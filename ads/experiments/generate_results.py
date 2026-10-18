from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT_DIR / "ads" / "results"
RAW_LOCUST_DIR = RESULTS_DIR / "raw" / "locust"
RAW_CPU_DIR = RESULTS_DIR / "raw" / "cpu"
PROCESSED_DIR = RESULTS_DIR / "processed"
CHARTS_DIR = RESULTS_DIR / "charts"

OPERATION_PATTERN = re.compile(r"(/api/customer/owners)/\d+$")
PROFILE_LABELS = {"leitura": "Leitura", "escrita": "Escrita"}
SCENARIO_USERS = {"A": 30, "B": 80, "C": 150}
COLORS = {"Leitura": "#2563eb", "Escrita": "#dc2626"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera tabelas e gráficos a partir dos resultados brutos do Locust."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=RESULTS_DIR,
        help="Diretório de resultados (padrão: ads/results).",
    )
    return parser.parse_args()


def normalize_operation(name: str) -> str:
    return OPERATION_PATTERN.sub(r"\1/{id}", name)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def number(value: str) -> float:
    return float(value or 0)


def integer(value: str) -> int:
    return int(float(value or 0))


def metadata_from_run(run_id: str) -> tuple[str, str, int, int]:
    profile, scenario, _, repetition = run_id.split("_")
    return profile, scenario, SCENARIO_USERS[scenario], int(repetition)


def locust_metric_rows(results_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    locust_dir = results_dir / "raw" / "locust"
    for path in sorted(locust_dir.glob("*_stats.csv")):
        run_id = path.name.removesuffix("_stats.csv")
        profile, scenario, users, repetition = metadata_from_run(run_id)
        for source in read_csv(path):
            operation = normalize_operation(source["Name"])
            requests = integer(source["Request Count"])
            failures = integer(source["Failure Count"])
            rows.append(
                {
                    "run_id": run_id,
                    "perfil": PROFILE_LABELS[profile],
                    "cenario": scenario,
                    "usuarios": users,
                    "repeticao": repetition,
                    "operacao": operation,
                    "requisicoes": requests,
                    "falhas": failures,
                    "tempo_medio_ms": number(source["Average Response Time"]),
                    "p95_ms": number(source["95%"]),
                    "vazao_req_s": number(source["Requests/s"]),
                    "taxa_falhas_percent": 100 * failures / requests if requests else 0,
                }
            )
    if not rows:
        raise FileNotFoundError(f"Nenhum *_stats.csv encontrado em {locust_dir}")
    return rows


def cpu_metric_rows(results_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cpu_dir = results_dir / "raw" / "cpu"
    for path in sorted(cpu_dir.glob("*_cpu.csv")):
        run_id = path.name.removesuffix("_cpu.csv")
        profile, scenario, users, repetition = metadata_from_run(run_id)
        samples = read_csv(path)
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for sample in samples:
            grouped[sample["servico"]].append(sample)
        for service, service_samples in grouped.items():
            cpu_values = [number(sample["cpu_percent"]) for sample in service_samples]
            memory_values = [number(sample["memory_percent"]) for sample in service_samples]
            rows.append(
                {
                    "run_id": run_id,
                    "perfil": PROFILE_LABELS[profile],
                    "cenario": scenario,
                    "usuarios": users,
                    "repeticao": repetition,
                    "servico": service,
                    "amostras": len(cpu_values),
                    "cpu_media_percent": mean(cpu_values),
                    "cpu_max_percent": max(cpu_values),
                    "memoria_media_percent": mean(memory_values),
                    "memoria_max_percent": max(memory_values),
                }
            )
    if not rows:
        raise FileNotFoundError(f"Nenhum *_cpu.csv encontrado em {cpu_dir}")
    return rows


def average_rows(rows: Iterable[dict[str, object]], group_fields: list[str], value_fields: list[str]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    result: list[dict[str, object]] = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        output = dict(zip(group_fields, key))
        output["repeticoes"] = len(group)
        for field in value_fields:
            output[field] = mean(float(row[field]) for row in group)
        result.append(output)
    return result


def aggregate_scenario_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return average_rows(
        [row for row in rows if row["operacao"] == "Aggregated"],
        ["perfil", "cenario", "usuarios"],
        [
            "tempo_medio_ms",
            "p95_ms",
            "vazao_req_s",
            "requisicoes",
            "falhas",
            "taxa_falhas_percent",
        ],
    )


def aggregate_operation_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return average_rows(
        [row for row in rows if row["operacao"] != "Aggregated"],
        ["perfil", "cenario", "usuarios", "operacao"],
        [
            "tempo_medio_ms",
            "p95_ms",
            "vazao_req_s",
            "requisicoes",
            "falhas",
            "taxa_falhas_percent",
        ],
    )


def aggregate_cpu_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return average_rows(
        rows,
        ["perfil", "cenario", "usuarios", "servico"],
        [
            "cpu_media_percent",
            "cpu_max_percent",
            "memoria_media_percent",
            "memoria_max_percent",
        ],
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: f"{value:.4f}" if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def import_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            "A biblioteca matplotlib não está instalada. "
            "Instale-a no ambiente do projeto com: python -m pip install matplotlib"
        ) from error
    return plt


def scenario_values(rows: list[dict[str, object]], profile: str, field: str) -> list[float]:
    return [
        float(next(row[field] for row in rows if row["perfil"] == profile and row["cenario"] == scenario))
        for scenario in ("A", "B", "C")
    ]


def save_line_chart(plt, rows, field: str, ylabel: str, title: str, filename: str) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    for profile in ("Leitura", "Escrita"):
        available = [row for row in rows if row["perfil"] == profile]
        scenarios = [scenario for scenario in ("A", "B", "C") if any(row["cenario"] == scenario for row in available)]
        values = [
            next(row[field] for row in available if row["cenario"] == scenario)
            for scenario in scenarios
        ]
        axis.plot(
            [SCENARIO_USERS[scenario] for scenario in scenarios],
            values,
            marker="o",
            linewidth=2.5,
            label=profile,
            color=COLORS[profile],
        )
    axis.set_title(title)
    axis.set_xlabel("Usuários simultâneos")
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(CHARTS_DIR / filename, dpi=160)
    plt.close(figure)


def save_grouped_bar(plt, rows, field: str, ylabel: str, title: str, filename: str) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    scenarios = ("A", "B", "C")
    positions = list(range(len(scenarios)))
    width = 0.36
    for offset, profile in enumerate(("Leitura", "Escrita")):
        values = [
            next(
                (float(row[field]) for row in rows if row["perfil"] == profile and row["cenario"] == scenario),
                0,
            )
            for scenario in scenarios
        ]
        axis.bar(
            [position + (offset - 0.5) * width for position in positions],
            values,
            width,
            label=profile,
            color=COLORS[profile],
        )
    axis.set_xticks(positions, [f"{scenario}\n{SCENARIO_USERS[scenario]} usuários" for scenario in scenarios])
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(CHARTS_DIR / filename, dpi=160)
    plt.close(figure)


def save_operation_degradation(plt, rows: list[dict[str, object]], profile: str) -> None:
    figure, axis = plt.subplots(figsize=(12, 7))
    profile_rows = [row for row in rows if row["perfil"] == profile]
    operations = sorted({str(row["operacao"]) for row in profile_rows})
    for operation in operations:
        values = []
        users = []
        for scenario in ("A", "B", "C"):
            matching = [row for row in profile_rows if row["operacao"] == operation and row["cenario"] == scenario]
            if matching:
                users.append(SCENARIO_USERS[scenario])
                values.append(float(matching[0]["tempo_medio_ms"]))
        axis.plot(users, values, marker="o", linewidth=2, label=operation)
    axis.set_title(f"Degradação por operação — Perfil {profile}")
    axis.set_xlabel("Usuários simultâneos")
    axis.set_ylabel("Tempo médio de resposta (ms)")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(CHARTS_DIR / f"degradacao_operacoes_{profile.lower()}.png", dpi=160)
    plt.close(figure)


def write_degradation_table(operation_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for profile in ("Leitura", "Escrita"):
        operations = sorted({str(row["operacao"]) for row in operation_rows if row["perfil"] == profile})
        for operation in operations:
            values = {}
            for scenario in ("A", "B", "C"):
                matching = next(
                    (
                        row
                        for row in operation_rows
                        if row["perfil"] == profile
                        and row["operacao"] == operation
                        and row["cenario"] == scenario
                    ),
                    None,
                )
                values[scenario] = float(matching["tempo_medio_ms"]) if matching else None
            if values["A"] is None or values["C"] is None:
                continue
            output.append(
                {
                    "perfil": profile,
                    "operacao": operation,
                    "tempo_A_ms": values["A"],
                    "tempo_B_ms": values["B"] or "",
                    "tempo_C_ms": values["C"],
                    "aumento_absoluto_ms": values["C"] - values["A"],
                    "aumento_percentual": 100 * (values["C"] - values["A"]) / values["A"] if values["A"] else 0,
                }
            )
    return output


def generate(results_dir: Path) -> None:
    global PROCESSED_DIR, CHARTS_DIR
    PROCESSED_DIR = results_dir / "processed"
    CHARTS_DIR = results_dir / "charts"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    locust_rows = locust_metric_rows(results_dir)
    cpu_rows = cpu_metric_rows(results_dir)
    scenario_rows = aggregate_scenario_rows(locust_rows)
    operation_rows = aggregate_operation_rows(locust_rows)
    cpu_averages = aggregate_cpu_rows(cpu_rows)
    degradation_rows = write_degradation_table(operation_rows)

    write_csv(PROCESSED_DIR / "repetitions_by_operation.csv", locust_rows)
    write_csv(PROCESSED_DIR / "averages_by_scenario.csv", scenario_rows)
    write_csv(PROCESSED_DIR / "averages_by_operation.csv", operation_rows)
    write_csv(PROCESSED_DIR / "cpu_averages.csv", cpu_averages)
    write_csv(PROCESSED_DIR / "degradation_by_operation.csv", degradation_rows)

    plt = import_matplotlib()
    save_line_chart(plt, scenario_rows, "tempo_medio_ms", "ms", "Tempo médio por quantidade de usuários", "tempo_medio_por_usuarios.png")
    save_line_chart(plt, scenario_rows, "p95_ms", "ms", "P95 por quantidade de usuários", "p95_por_usuarios.png")
    save_line_chart(plt, scenario_rows, "vazao_req_s", "req/s", "Vazão por quantidade de usuários", "vazao_por_usuarios.png")
    save_grouped_bar(plt, scenario_rows, "requisicoes", "requisições", "Total de requisições por cenário", "total_requisicoes_por_cenario.png")
    save_grouped_bar(plt, scenario_rows, "taxa_falhas_percent", "%", "Taxa de falhas por cenário", "taxa_falhas_por_cenario.png")
    save_operation_degradation(plt, operation_rows, "Leitura")
    save_operation_degradation(plt, operation_rows, "Escrita")

    for service in sorted({str(row["servico"]) for row in cpu_averages}):
        service_rows = [row for row in cpu_averages if row["servico"] == service]
        save_line_chart(
            plt,
            service_rows,
            "cpu_media_percent",
            "%",
            f"CPU média — {service}",
            f"cpu_{service}.png",
        )
    print(f"Resultados processados em: {PROCESSED_DIR}")
    print(f"Gráficos gerados em: {CHARTS_DIR}")


def main() -> int:
    args = parse_args()
    try:
        generate(args.results_dir)
    except (FileNotFoundError, RuntimeError, KeyError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
