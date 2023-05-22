from dataclasses import dataclass, field
import re
from typing import Any

from requests import get, post

BASE_URL = "https://buildkite.com/retool"
BUILD_FINISHED_STATES = ["SKIPPED", "PASSED", "FAILED", "CANCELED"]
BUILD_RUNNING_STATES = [
    "CREATING",
    "RUNNING",
    "FAILING",
    "CANCELING",
    "BLOCKED",
    "SCHEDULED",
]

JOB_FINISHED_STATES = [
    "BLOCKED_FAILED",
    "UNBLOCKED_FAILED",
    "FINISHED",
    "CANCELED",
    "TIMED_OUT",
    "SKIPPED",
]


@dataclass
class Pipeline:
    name: str
    color: str
    slug: str


@dataclass
class Job:
    state: str
    passed: bool


@dataclass
class Build:
    number: int
    commit_message: str
    pipeline: Pipeline
    state: str
    jobs: list[Job] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.pipeline.slug}/builds/{self.number}"


class BuildkiteNotFoundException(Exception):
    pass


class Buildkite:
    rest_base_url: str = "https://api.buildkite.com/v2"
    graphql_base_url: str = "https://graphql.buildkite.com/v1"

    def __init__(self, org_name: str, buildkite_token: str) -> None:
        super().__init__()
        self.org_name = org_name
        self.headers = {
            "Authorization": f"Bearer {buildkite_token}",
            "Content-Type": "application/json",
        }

    def _graphql_post(self, query: str, variables: dict[str, Any]) -> dict:
        response = post(
            self.graphql_base_url,
            headers=self.headers,
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        return response.json()

    def _rest_post(self, url: str, body: dict) -> dict:
        response = post(url, headers=self.headers, json=body)
        response.raise_for_status()
        return response.json()

    def _rest_get(self, url: str, **kwargs: dict) -> dict:
        response = get(url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_job_artifact_count(self, job_id: str) -> int:
        query = """
        query getJobArtifactCount($job_id: ID!) {
            job(uuid: $job_id) {
                ... on JobTypeCommand {
                    artifacts {
                        count
                    }
                }
            }
        }
        """
        variables = {"job_id": job_id}
        result = self._graphql_post(query=query, variables=variables)
        return result["data"]["job"]["artifacts"]["count"]

    def get_job_artifacts(
        self, job_id: str, regex_filter: str | None = None
    ) -> list[dict]:
        artifact_count = self.get_job_artifact_count(job_id=job_id)
        if artifact_count == 0:
            return []

        query = """
        query getJobArtfacts($job_id: ID!, $artifact_count: Int) {
            job(uuid: $job_id) {
                ... on JobTypeCommand {
                    artifacts(first: $artifact_count) {
                        edges {
                            node {
                                downloadURL
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {"job_id": job_id, "artifact_count": artifact_count}
        result = self._graphql_post(query=query, variables=variables)
        return [
            edge["node"]
            for edge in result["data"]["job"]["artifacts"]["edges"]
            if regex_filter is None
            or re.search(regex_filter, edge["node"]["downloadURL"])
        ]

    def get_build_data(self, pipeline_slug: str, build_id: int) -> dict:
        url = f"{self.rest_base_url}/organizations/{self.org_name}/pipelines/{pipeline_slug}/builds/{build_id}?include_retried_jobs=true"
        return self._rest_get(url=url)

    def get_artifact_content(self, artifact_url: str) -> bytes:
        response = get(artifact_url, headers=self.headers, allow_redirects=True)
        response.raise_for_status()
        return response.content

    def create_build(self, pipeline_slug: str, env: dict) -> dict:
        url = f"{self.rest_base_url}/organizations/{self.org_name}/pipelines/{pipeline_slug}/builds"
        result = self._rest_post(url=url, body=env)
        return result

    def get_build_url_from_commit(self, commit_sha: str) -> str:
        query = """
        query getBuildFromCommit($commit_sha: [String!]) {
            pipeline(slug:"retool/retool-development-dot-tests"){
                builds(commit: $commit_sha) {
                    edges {
                        node {
                            url
                        }
                    }
                }
            }
        }
        """
        variables = {"commit_sha": commit_sha}
        result = self._graphql_post(query=query, variables=variables)
        data = result["data"]
        if not data["pipeline"]["builds"]["edges"]:
            raise BuildkiteNotFoundException(f"No build found for commit {commit_sha}")
        return result["data"]["pipeline"]["builds"]["edges"][0]["node"]["url"]

    def get_build_url_from_branch(self, branch: str) -> str:
        query = """
        query getBuildFromBranch($branch: [String!]) {
            pipeline(slug:"retool/retool-development-dot-tests"){
                builds(branch: $branch) {
                    edges {
                        node {
                            url
                        }
                    }
                }
            }
        }
        """
        variables = {"branch": branch}
        result = self._graphql_post(query=query, variables=variables)
        data = result["data"]
        if not data["pipeline"]["builds"]["edges"]:
            raise BuildkiteNotFoundException(f"No build found for branch {branch}")
        return result["data"]["pipeline"]["builds"]["edges"][0]["node"]["url"]

    def get_user_builds(
        self, limit: int = 10, show_finished: bool = False
    ) -> list[Build]:
        query = """
        query GetUserBuilds($limit: Int, $state_filter: [BuildStates!]) {
            viewer {
                user {
                    builds(first: $limit, state: $state_filter) {
                        edges {
                            node {
                                pipeline {
                                    name
                                    color
                                    slug
                                }
                                message
                                number
                                state
                                jobs(first: 100) {
                                    edges {
                                        node {
                                            ... on JobTypeCommand {
                                                state
                                                passed
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        if show_finished:
            state_filters = []
        else:
            state_filters = BUILD_RUNNING_STATES

        variables = {
            "limit": limit,
            "state_filter": state_filters,
        }
        result = self._graphql_post(query=query, variables=variables)
        data = result["data"]
        builds = []
        for build_edge in data["viewer"]["user"]["builds"]["edges"]:
            build_node = build_edge["node"]
            jobs = []
            for job_edge in build_node["jobs"]["edges"]:
                job_node = job_edge["node"]
                jobs.append(Job(state=job_node["state"], passed=job_node["passed"]))

            pipeline = Pipeline(
                name=build_node["pipeline"]["name"],
                color=build_node["pipeline"]["color"],
                slug=build_node["pipeline"]["slug"],
            )
            builds.append(
                Build(
                    commit_message=build_node["message"],
                    number=build_node["number"],
                    pipeline=pipeline,
                    state=build_node["state"],
                    jobs=jobs,
                )
            )

        return builds
