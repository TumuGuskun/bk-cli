import os
import subprocess
from typing import Optional
import click
import webbrowser

from gum import gum_choose

from bk import Buildkite, BuildkiteNotFoundException
from display import display_build


@click.group()
@click.pass_context
def kite(ctx: click.Context) -> None:
    buildkite = Buildkite(
        org_name="retool", buildkite_token=os.getenv("BUILDKITE_TOKEN", "")
    )
    ctx.ensure_object(dict)
    ctx.obj["BUILDKITE"] = buildkite


@kite.command()
@click.pass_context
@click.argument("commit", required=False)
def commit(ctx: click.Context, commit: Optional[str]) -> None:
    buildkite = ctx.obj["BUILDKITE"]
    if not commit:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True
        ).stdout.strip()
    try:
        url = buildkite.get_build_url_from_commit(commit_sha=commit)
    except BuildkiteNotFoundException as e:
        print(e)
    else:
        webbrowser.open(url)


@kite.command()
@click.argument("branch", required=False)
@click.pass_context
def branch(ctx: click.Context, branch: Optional[str]) -> None:
    buildkite = ctx.obj["BUILDKITE"]
    if not branch:
        branch = subprocess.run(
            ["git", "branch", "--show-current"], stdout=subprocess.PIPE, text=True
        ).stdout.strip()
    try:
        url = buildkite.get_build_url_from_branch(branch=branch)
    except BuildkiteNotFoundException as e:
        print(e)
    else:
        webbrowser.open(url)


@kite.command()
@click.argument("build_number")
def build(build_number: int) -> None:
    url = f"https://buildkite.com/retool/retool-development-dot-tests/builds/{build_number}"
    webbrowser.open(url)


@kite.command()
@click.option("--show-finished", is_flag=True, show_default=True)
@click.option("--limit", default=10, help="Limit the number of builds")
@click.pass_context
def builds(ctx: click.Context, limit: int, show_finished: bool) -> None:
    buildkite: Buildkite = ctx.obj["BUILDKITE"]
    builds = buildkite.get_user_builds(limit=limit, show_finished=show_finished)

    if not builds:
        print("No builds found, use --show-finished to show previous builds")
    build_choice = gum_choose(choices=builds, display_function=display_build).selection
    webbrowser.open(build_choice.url)
