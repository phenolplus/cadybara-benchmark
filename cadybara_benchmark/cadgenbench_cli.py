from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cadybara_benchmark.cadgenbench import CadGenBenchSeries, create_cadgenbench_experiment


app = typer.Typer()


@app.callback(invoke_without_command=True)
def import_cadgenbench(
    data_dir: Annotated[Path, typer.Option(help="Path to cadgenbench-data")] = Path(
        "cadgenbench-data"
    ),
    series: Annotated[
        str,
        typer.Option(
            help="CadGenBench series to import: 100, 200, or both.",
            case_sensitive=False,
        ),
    ] = "both",
    folder: Annotated[
        list[int] | None,
        typer.Option("--folder", "-f", help="Specific folder id to include. Repeat for many."),
    ] = None,
    name: Annotated[str | None, typer.Option()] = None,
    description: Annotated[str, typer.Option()] = "",
    category: Annotated[str, typer.Option()] = "",
    model: Annotated[
        str | None,
        typer.Option("--model", help="Experiment setup model default."),
    ] = None,
    response_mode: Annotated[
        str | None,
        typer.Option("--response-mode", help="Experiment setup response mode."),
    ] = None,
    return_format: Annotated[
        str | None,
        typer.Option("--return-format", help="Experiment setup return format."),
    ] = None,
    linear_deflection: Annotated[
        float | None,
        typer.Option("--linear-deflection", help="Experiment setup linear deflection."),
    ] = None,
    angular_deflection: Annotated[
        float | None,
        typer.Option("--angular-deflection", help="Experiment setup angular deflection."),
    ] = None,
) -> None:
    try:
        experiment = create_cadgenbench_experiment(
            data_dir=data_dir,
            series=_parse_series(series),
            folder_ids=folder,
            name=name,
            description=description,
            category=category,
            model=model,
            response_mode=response_mode,
            return_format=return_format,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
        )
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Created experiment {experiment['id']}: {experiment['name']} "
        f"with {len(experiment.get('queries', []))} query line(s)"
    )


def _parse_series(series: str) -> list[CadGenBenchSeries]:
    series_value = series.lower()
    if series_value == "both":
        return ["100", "200"]
    if series_value in {"100", "200"}:
        return [series_value]  # type: ignore[list-item]
    raise ValueError("Series must be 100, 200, or both.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
