#!/usr/bin/env python3
import click
import docker
import os


def echo(txt):
    click.echo("-" * 79)
    click.echo(txt)
    click.echo("-" * 79)


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.option('--base', help="BaseName")
@click.option('--build-org', default="dafire", help="Build Organisation")
@click.pass_context
def cli(ctx, debug, base, build_org):
    ctx.obj['debug'] = debug
    ctx.obj['build_org'] = build_org
    ctx.obj['base'] = base
    click.echo('Debug mode is %s' % ('on' if debug else 'off'))


@cli.command()
def list():
    click.secho("hi", fg='green')
    c = docker.Client(base_url='unix://var/run/docker.sock',
                      version='1.12', timeout=10)

    cons = c.containers()
    for l in cons:
        print(l)


@cli.command()
def run():
    click.secho("hi", fg='green')
    c = docker.Client(base_url='unix://var/run/docker.sock',
                      version='1.12', timeout=10)

    cons = c.create_container("dafire/test")
    for l in cons:
        print(l)


@cli.command()
def build():
    click.secho("hi", fg='green')
    c = docker.Client(base_url='unix://var/run/docker.sock',
                      version='1.12', timeout=10)

    line = c.build(path="/vagrant/testgit", tag="test123", quiet=True, nocache=False, rm=True, stream=True)

    for l in line:
        click.echo("l %r %r" % (l, len(l)))


@cli.command()
@click.pass_obj
@click.option('--repo', help="RepoPath")
def create(obj, repo):
    c = docker.Client(base_url='unix://var/run/docker.sock',
                      version='1.12', timeout=20)

    tag = "%s/%s" % (obj.get("build_org"), obj.get("base"))

    # find old running container
    echo("Looking for running containers")
    running_containers = []
    for check in c.containers():
        if check.get("Image") == "%s:latest" % tag:
            click.echo("Found %s (%s)" % (check.get("Id"), check.get("Status")))
            running_containers.append(check.get("Id"))
    if not len(running_containers):
        click.echo("non found.")

    # build docker
    echo('Building Dockerfile')
    line = c.build(path=repo, tag=tag, quiet=True, nocache=False, rm=True, stream=True)

    for l in line:
        click.echo("l %r %r" % (l, len(l)))

    # create container
    echo("Creating Docker Container")

    container = c.create_container(tag, detach=True,ports=[80, 22])
    click.echo("container %r" % container)

    echo("Configuring Stuff")
    info = c.inspect_image(tag)
    binds = {}
    volumes = info.get("ContainerConfig").get("Volumes")
    for vol in volumes:
        vpath = os.path.join(os.getcwd(),"VOLUMES",vol[1:])
        os.makedirs(vpath, exist_ok=True)
        binds[vpath] = {
            'bind': vol,
            'ro': False
        }
    click.echo("Binds %r"%binds)

    # stopping old containers
    if len(running_containers):
        echo("Stopping old containers")
        for cont in running_containers:
            res = c.stop(cont)

    # start container
    echo("Starting Container")
    start = c.start(container.get("Id"),publish_all_ports=True, binds=binds)
    click.echo(start)

    click.echo(os.getcwd())


if __name__ == '__main__':
    cli(obj={})
