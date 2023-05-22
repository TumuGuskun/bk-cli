from bk import JOB_FINISHED_STATES, Build


def display_build(build: Build) -> str:
    total_jobs = len(build.jobs)
    finished_jobs = sum(1 for job in build.jobs if job.state in JOB_FINISHED_STATES)

    output = f"{build.pipeline.name : <50} {build.number : <10}"
    output += f"{finished_jobs * 100/total_jobs : >6.0f}% finished    {'State: ' + build.state : <20}".rstrip()
    return output
