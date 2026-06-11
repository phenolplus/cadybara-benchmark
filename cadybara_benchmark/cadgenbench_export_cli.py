from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cadybara_benchmark.cadgenbench_export import export_cadgenbench_submission


def export_cadgenbench(
    experiment_id: Annotated[str, typer.Argument(help="Experiment id containing the run.")],
    run_id: Annotated[str, typer.Argument(help="Run id to export.")],
    destination: Annotated[Path, typer.Argument(help="Destination package folder.")],
    series: Annotated[
        str,
        typer.Option(
            "--series",
            help="CadGenBench series to export: 100, 200, or both.",
            case_sensitive=False,
        ),
    ] = "both",
    submitter_name: Annotated[
        str,
        typer.Option("--submitter-name", help="meta.json submitter_name."),
    ] = "Cadybara Benchmark",
    submission_name: Annotated[
        str | None,
        typer.Option("--submission-name", help="meta.json submission_name."),
    ] = None,
    agent_url: Annotated[
        str | None,
        typer.Option("--agent-url", help="meta.json agent_url."),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help="meta.json notes."),
    ] = None,
    agree_to_publish: Annotated[
        bool,
        typer.Option("--agree-to-publish/--no-agree-to-publish", help="meta.json consent flag."),
    ] = True,
    render_step: Annotated[
        bool,
        typer.Option(
            "--render-step/--no-render-step",
            help="Render output.step from generated_code.py with CadQuery when available.",
        ),
    ] = False,
    copy: Annotated[
        bool,
        typer.Option(
            "--copy/--no-copy",
            help="For 200-series samples without an exported STEP, copy cadgenbench-data input.step.",
        ),
    ] = False,
    data_dir: Annotated[
        Path,
        typer.Option("--data-dir", help="Path to cadgenbench-data for --copy fallback."),
    ] = Path("cadgenbench-data"),
) -> None:
    try:
        result = export_cadgenbench_submission(
            experiment_id,
            run_id,
            destination,
            series=series.lower(),  # type: ignore[arg-type]
            submitter_name=submitter_name,
            submission_name=submission_name,
            agent_url=agent_url,
            notes=notes,
            agree_to_publish=agree_to_publish,
            render_step=render_step,
            copy=copy,
            data_dir=data_dir,
        )
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"Exported {result['count']} CadGenBench sample folder(s) to {result['destination']} "
        f"({result['with_output_step']} with output.step)"
    )


def main() -> None:
    typer.run(export_cadgenbench)


if __name__ == "__main__":
    main()
