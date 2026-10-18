from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
LOCUSTFILE = ROOT_DIR / "ads" / "locustfile.py"
RESULTS_DIR = ROOT_DIR / "ads" / "results"
RAW_LOCUST_DIR = RESULTS_DIR / "raw" / "locust"
RAW_CPU_DIR = RESULTS_DIR / "raw" / "cpu"
RAW_METADATA_DIR = RESULTS_DIR / "raw" / "metadata"

WARMUP_SECONDS = 60
MEASUREMENT_SECONDS = 6 * 60
DEFAULT_SPAWN_RATE = 10
CPU_SAMPLE_INTERVAL_SECONDS = 5


@dataclass(frozen=True)
class Scenario:
    name: str
    users: int


SCENARIOS = (
    Scenario("A", 30),
    Scenario("B", 80),
    Scenario("C", 150),
)

PROFILES = ("leitura", "escrita")
CPU_SERVICES = ("customers-service", "vets-service")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id(profile: str, scenario: Scenario, repetition: int) -> str:
    return f"{profile}_{scenario.name}_rep_{repetition:02d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa manualmente os experimentos do Locust do Trabalho 06."
    )
    parser.add_argument(
        "--locust-command",
        default="locust",
        help="Comando do Locust (padrão: locust; use .venv/Scripts/locust.exe se necessário).",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=10,
        help="Número de repetições por perfil/cenário (padrão: 10).",
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        default=DEFAULT_SPAWN_RATE,
        help=f"Taxa de criação de usuários por segundo (padrão: {DEFAULT_SPAWN_RATE}).",
    )
    parser.add_argument(
        "--cpu-interval",
        type=float,
        default=CPU_SAMPLE_INTERVAL_SECONDS,
        help=f"Intervalo entre amostras do docker stats em segundos (padrão: {CPU_SAMPLE_INTERVAL_SECONDS}).",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        help="Executa somente este perfil; sem a opção, executa os dois.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(scenario.name for scenario in SCENARIOS),
        help="Executa somente este cenário; sem a opção, executa A, B e C.",
    )
    parser.add_argument(
        "--repetition",
        type=int,
        help="Executa somente esta repetição; sem a opção, executa todas.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.repetitions < 1:
        raise ValueError("--repetitions deve ser maior ou igual a 1.")
    if args.spawn_rate < 1:
        raise ValueError("--spawn-rate deve ser maior ou igual a 1.")
    if args.cpu_interval <= 0:
        raise ValueError("--cpu-interval deve ser maior que zero.")
    if args.repetition is not None and not 1 <= args.repetition <= args.repetitions:
        raise ValueError("--repetition deve estar entre 1 e --repetitions.")
    if not LOCUSTFILE.is_file():
        raise FileNotFoundError(f"Locustfile não encontrado: {LOCUSTFILE}")
    if shutil.which("docker") is None:
        raise RuntimeError("Docker não encontrado no PATH.")
    if shutil.which(args.locust_command) is None and not Path(args.locust_command).is_file():
        raise RuntimeError(
            f"Comando do Locust não encontrado: {args.locust_command}. "
            "Ative o ambiente virtual ou informe --locust-command."
        )


def ensure_output_directories() -> None:
    for directory in (RAW_LOCUST_DIR, RAW_CPU_DIR, RAW_METADATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def execute(command: list[str], *, stdout: Any = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=True,
        text=True,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE,
    )


def start_locust(
    locust_command: str,
    profile: str,
    users: int,
    duration_seconds: int,
    spawn_rate: int,
    csv_prefix: Path | None,
) -> subprocess.Popen[str]:
    command = [
        locust_command,
        "-f",
        str(LOCUSTFILE),
        "PerfilLeitura" if profile == "leitura" else "PerfilEscrita",
        "--headless",
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        f"{duration_seconds}s",
        "--host",
        "http://localhost:8080",
        "--only-summary",
    ]
    if csv_prefix is not None:
        command.extend(["--csv", str(csv_prefix), "--csv-full-history"])

    return subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stream_process_output(process: subprocess.Popen[str], destination: Path) -> Thread:
    def copy_output() -> None:
        assert process.stdout is not None
        with destination.open("w", encoding="utf-8") as output:
            for line in process.stdout:
                output.write(line)

    thread = Thread(target=copy_output, daemon=True)
    thread.start()
    return thread


def wait_for_process(process: subprocess.Popen[str], phase: str) -> None:
    return_code = process.wait()
    if return_code == 1:
        print(
            f"Aviso: Locust terminou a fase de {phase} com requisições falhas; "
            "os resultados serão preservados."
        )
    elif return_code != 0:
        raise RuntimeError(f"Locust falhou durante a fase de {phase} (código {return_code}).")


def parse_cpu_value(value: str) -> float:
    return float(value.strip().rstrip("%"))


def sample_docker_stats(
    run_identifier: str,
    profile: str,
    scenario: Scenario,
    repetition: int,
    interval_seconds: float,
    stop_event: Event,
    output_path: Path,
    errors: list[BaseException],
) -> None:
    fields = [
        "run_id",
        "perfil",
        "cenario",
        "usuarios",
        "repeticao",
        "timestamp",
        "servico",
        "cpu_percent",
        "memory_usage",
        "memory_percent",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        while not stop_event.is_set():
            timestamp = utc_now()
            try:
                result = execute(
                    [
                        "docker",
                        "stats",
                        "--no-stream",
                        "--format",
                        "{{json .}}",
                        *CPU_SERVICES,
                    ]
                )
                for line in result.stdout.splitlines():
                    if not line.strip():
                        continue
                    container = json.loads(line)
                    service = container.get("Name", "")
                    if service not in CPU_SERVICES:
                        continue
                    writer.writerow(
                        {
                            "run_id": run_identifier,
                            "perfil": profile,
                            "cenario": scenario.name,
                            "usuarios": scenario.users,
                            "repeticao": repetition,
                            "timestamp": timestamp,
                            "servico": service,
                            "cpu_percent": parse_cpu_value(container["CPUPerc"]),
                            "memory_usage": container["MemUsage"],
                            "memory_percent": parse_cpu_value(container["MemPerc"]),
                        }
                    )
                output.flush()
            except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as error:
                errors.append(RuntimeError(f"Falha ao coletar docker stats: {error}"))
                stop_event.set()
                return
            stop_event.wait(interval_seconds)


def write_metadata(
    run_identifier: str,
    profile: str,
    scenario: Scenario,
    repetition: int,
    started_at: str,
    ended_at: str,
    locust_prefix: Path,
    cpu_path: Path,
) -> None:
    metadata = {
        "run_id": run_identifier,
        "perfil": profile,
        "cenario": scenario.name,
        "usuarios": scenario.users,
        "repeticao": repetition,
        "aquecimento_segundos": WARMUP_SECONDS,
        "medicao_segundos": MEASUREMENT_SECONDS,
        "inicio_utc": started_at,
        "fim_utc": ended_at,
        "locust_csv_prefix": str(locust_prefix),
        "cpu_csv": str(cpu_path),
        "servicos_cpu": list(CPU_SERVICES),
    }
    metadata_path = RAW_METADATA_DIR / f"{run_identifier}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_experiment(
    args: argparse.Namespace,
    profile: str,
    scenario: Scenario,
    repetition: int,
) -> None:
    identifier = run_id(profile, scenario, repetition)
    locust_prefix = RAW_LOCUST_DIR / identifier
    cpu_path = RAW_CPU_DIR / f"{identifier}_cpu.csv"
    log_path = RAW_LOCUST_DIR / f"{identifier}_output.log"
    started_at = utc_now()

    print(f"[{identifier}] aquecimento: {WARMUP_SECONDS}s")
    warmup = start_locust(
        args.locust_command,
        profile,
        scenario.users,
        WARMUP_SECONDS,
        args.spawn_rate,
        None,
    )
    warmup_output = stream_process_output(warmup, log_path)
    wait_for_process(warmup, "aquecimento")
    warmup_output.join()

    print(f"[{identifier}] medição: {MEASUREMENT_SECONDS}s")
    measurement = start_locust(
        args.locust_command,
        profile,
        scenario.users,
        MEASUREMENT_SECONDS,
        args.spawn_rate,
        locust_prefix,
    )
    measurement_output = stream_process_output(measurement, log_path)
    stop_cpu_sampling = Event()
    cpu_errors: list[BaseException] = []
    cpu_thread = Thread(
        target=sample_docker_stats,
        args=(
            identifier,
            profile,
            scenario,
            repetition,
            args.cpu_interval,
            stop_cpu_sampling,
            cpu_path,
            cpu_errors,
        ),
        daemon=True,
    )
    cpu_thread.start()
    try:
        wait_for_process(measurement, "medição")
    finally:
        stop_cpu_sampling.set()
        cpu_thread.join()
        measurement_output.join()
    if cpu_errors:
        raise RuntimeError(str(cpu_errors[0]))

    write_metadata(
        identifier,
        profile,
        scenario,
        repetition,
        started_at,
        utc_now(),
        locust_prefix,
        cpu_path,
    )
    print(f"[{identifier}] concluído")


def selected_profiles(args: argparse.Namespace) -> tuple[str, ...]:
    return (args.profile,) if args.profile else PROFILES


def selected_scenarios(args: argparse.Namespace) -> tuple[Scenario, ...]:
    if args.scenario:
        return tuple(scenario for scenario in SCENARIOS if scenario.name == args.scenario)
    return SCENARIOS


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        ensure_output_directories()
        repetitions = (args.repetition,) if args.repetition else range(1, args.repetitions + 1)
        total = len(selected_profiles(args)) * len(selected_scenarios(args)) * len(repetitions)
        completed = 0
        print(f"Serão executadas {total} configuração(ões).")
        print("A aplicação deve estar previamente disponível em http://localhost:8080.")
        for profile in selected_profiles(args):
            for scenario in selected_scenarios(args):
                for repetition in repetitions:
                    run_experiment(args, profile, scenario, repetition)
                    completed += 1
                    print(f"Progresso: {completed}/{total}")
    except (KeyboardInterrupt, subprocess.CalledProcessError) as error:
        print(f"Execução interrompida: {error}", file=sys.stderr)
        return 130
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    raise SystemExit(main())
