from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cadybara_benchmark.config import get_settings
from cadybara_benchmark.publishing import publish_experiment
from cadybara_benchmark.services.analysis import analyze_experiment
from cadybara_benchmark.services.direct import submit_query
from cadybara_benchmark.services.experiments import (
    create_experiment as create_experiment_service,
    get_experiment,
    list_experiments as list_experiments_service,
)
from cadybara_benchmark.services.queries import (
    add_query as add_query_service,
    list_queries as list_queries_service,
)
from cadybara_benchmark.services.runs import (
    list_results_for_experiment,
    list_runs,
    run_experiment,
)


app = typer.Typer(no_args_is_help=True)


def _handle_error(exc: Exception) -> None:
    raise typer.Exit(code=1) from exc


@app.command("create-experiment")
def create_experiment(
    name: Annotated[str | None, typer.Option(prompt=True)] = None,
    description: Annotated[str, typer.Option()] = "",
    type: Annotated[str, typer.Option()] = "query_comparison",
) -> None:
    try:
        experiment = create_experiment_service(name or "", description, type)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(f"Created experiment {experiment['id']}: {experiment['name']}")


@app.command("list-experiments")
def list_experiments() -> None:
    experiments = list_experiments_service()
    if not experiments:
        typer.echo("No experiments found.")
        return
    typer.echo("ID      STATUS                 TYPE              UPDATED              NAME")
    for experiment in experiments:
        typer.echo(
            f"{experiment['id']:<7} {experiment['status']:<22} {experiment['type']:<17} "
            f"{experiment['updated_at']:<20} {experiment['name']}"
        )


@app.command("show-experiment")
def show_experiment(experiment_id: str) -> None:
    try:
        experiment = get_experiment(experiment_id)
        queries = list_queries_service(experiment_id)
        runs = list_runs(experiment_id)
        results = list_results_for_experiment(experiment_id)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(f"{experiment['id']}: {experiment['name']}")
    typer.echo(f"Status: {experiment['status']}")
    typer.echo(f"Type: {experiment['type']}")
    typer.echo(f"Queries: {len(queries)}")
    typer.echo(f"Runs: {len(runs)}")
    typer.echo(f"Results: {len(results)}")
    typer.echo(f"Setup: {experiment['setup']}")


@app.command("add-query")
def add_query(
    experiment_id: str,
    text: Annotated[str | None, typer.Option(prompt=True)] = None,
    category: Annotated[str, typer.Option()] = "",
    model: Annotated[str | None, typer.Option()] = None,
    image_path: Annotated[list[Path] | None, typer.Option(help="Reference image file(s)")] = None,
) -> None:
    try:
        query = add_query_service(
            experiment_id,
            text or "",
            category,
            model,
            image_paths=image_path,
        )
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(f"Created query {query['id']} for {experiment_id}")


@app.command("list-queries")
def list_queries(experiment_id: str) -> None:
    try:
        queries = list_queries_service(experiment_id)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    if not queries:
        typer.echo("No queries found.")
        return
    typer.echo("ID    MODEL                           CATEGORY          TEXT")
    for query in queries:
        text = query["text"]
        if len(text) > 80:
            text = f"{text[:77]}..."
        model = query["model"] or "(default)"
        typer.echo(
            f"{query['id']:<5} {model:<31} {query['category']:<17} {text}"
        )


@app.command("run")
def run(
    experiment_id: str,
    model: Annotated[str | None, typer.Option()] = None,
    linear_deflection: Annotated[float | None, typer.Option()] = None,
    angular_deflection: Annotated[float | None, typer.Option()] = None,
    response_mode: Annotated[str, typer.Option()] = "json",
) -> None:
    settings = get_settings()
    try:
        settings.require_api_key()
        parameters = {"response_mode": response_mode}
        if linear_deflection is not None:
            parameters["linear_deflection"] = linear_deflection
        if angular_deflection is not None:
            parameters["angular_deflection"] = angular_deflection

        def progress(event: str, payload: dict) -> None:
            if event == "started":
                typer.echo(
                    f"Started {payload['query_id']} in {payload['run_id']}"
                )
            elif event == "completed":
                typer.echo(f"Completed {payload['query_id']} in {payload['run_id']}")
            elif event == "failed":
                typer.echo(f"Failed {payload['query_id']} in {payload['run_id']}")

        summary = run_experiment(
            experiment_id, model, parameters, settings=settings, on_event=progress
        )
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(
        f"Ran {experiment_id}: {summary['completed']} completed, {summary['failed']} failed "
        f"(run {summary['run_id']})"
    )


@app.command("submit-query")
def submit_query_command(
    text: Annotated[str | None, typer.Option(prompt=True)] = None,
    model: Annotated[str | None, typer.Option()] = None,
    linear_deflection: Annotated[float | None, typer.Option()] = None,
    angular_deflection: Annotated[float | None, typer.Option()] = None,
    response_mode: Annotated[str, typer.Option()] = "json",
) -> None:
    try:
        parameters = {"response_mode": response_mode}
        if model:
            parameters["model"] = model
        if linear_deflection is not None:
            parameters["linear_deflection"] = linear_deflection
        if angular_deflection is not None:
            parameters["angular_deflection"] = angular_deflection
        result = submit_query(text or "", parameters)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(f"Submitted direct query {result['submission_id']}")
    typer.echo(f"STL: {result['stl_path']}")
    typer.echo(f"Response: {result['response_path']}")
    typer.echo(f"Metadata: {result['metadata_path']}")


@app.command("analyze")
def analyze(experiment_id: str) -> None:
    try:
        report = analyze_experiment(experiment_id)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    average = report["summary"]["average_overall_score"]
    typer.echo(f"Analyzed {experiment_id}. Average overall score: {average}")
    typer.echo(f"Report: {report['report_path']}")


@app.command("publish")
def publish(
    experiment_id: str,
    run_id: Annotated[str | None, typer.Option()] = None,
) -> None:
    try:
        result = publish_experiment(experiment_id, run_id)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        _handle_error(exc)
    typer.echo(f"Published {result['count']} run(s).")
    for path in result["published"]:
        typer.echo(path)


@app.command("web")
def web(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option()] = False,
) -> None:
    import uvicorn

    uvicorn.run("cadybara_benchmark.web:app", host=host, port=port, reload=reload)
