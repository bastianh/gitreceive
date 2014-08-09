#!/usr/bin/env python3
import click
import docker
import json
import os
import yaml
import subprocess

from utils import nginx as nginx_config_manager
from db import get_engine, Base, DbContainer


def echo(txt):
    click.echo("=" * 79)
    click.echo(txt)
    click.echo("- " * 39 + "-")


def get_docker_client():
    return docker.Client(base_url='unix://var/run/docker.sock', version='1.12', timeout=20)


def get_database_session():
    directory = click.get_app_dir("mydeploy")
    os.makedirs(directory, exist_ok=True)
    cfg = os.path.join(directory, 'database.db')
    (engine, sessionmaker) = get_engine(cfg)
    Base.metadata.create_all(engine)
    click.echo(cfg)
    return sessionmaker()


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.option('--build-org', default="dafire", help="Build Organisation")
@click.pass_context
def cli(ctx, debug, build_org):
    ctx.obj['debug'] = debug
    ctx.obj['build_org'] = build_org
    ctx.obj['db'] = get_database_session()
    click.echo('Debug mode is %s' % ('on' if debug else 'off'))


@cli.command()
def list():
    c = get_docker_client()
    cons = c.containers()
    for l in cons:
        print(json.loads(l))


def create_nginx_config(session, docker):
    nginx_config = nginx_config_manager.Conf()
    container = {}
    for row in docker.containers():
        container[row["Id"]] = row
    for dbcontainer in session.query(DbContainer).order_by(DbContainer.created).group_by(DbContainer.image).all():
        if not dbcontainer.container_id in container:
            click.secho("Container %r not running. (Image %r)" % (dbcontainer.container_id, dbcontainer.image),
                        fg="red")
            # TODO: start container
            continue
        inspect = docker.inspect_container(dbcontainer.container_id)
        settings = {"CONTAINER_IP": inspect["NetworkSettings"]["IPAddress"]}

        nginx_server = nginx_config_manager.Server()
        ngx = json.loads(dbcontainer.config).get("nginx")
        for keys in ngx.get("keys"):
            for k, v in keys.items():
                nginx_server.add(nginx_config_manager.Key(k, v.format(**settings)))

        for l, keys_array in ngx.get("locations").items():
            nginx_location = nginx_config_manager.Location(l)
            for keys in keys_array:
                for k, v in keys.items():
                    nginx_location.add(nginx_config_manager.Key(k, v.format(**settings)))
            nginx_server.add(nginx_location)
        nginx_config.add(nginx_config_manager.Comment("Server %r" % dbcontainer.image))
        nginx_config.add(nginx_server)

    return nginx_config_manager.dumps(nginx_config)


@cli.command()
@click.pass_obj
def nginx(obj):
    session = obj.get("db")
    docker = get_docker_client()
    print(create_nginx_config(session, docker))


@cli.command()
@click.pass_obj
@click.argument('repository', type=click.Path(exists=True, file_okay=False))
@click.argument('basename')
@click.option('--nginx', type=click.File('w', encoding='utf-8'))
def gitreceive(obj, repository, basename, nginx):
    docker = get_docker_client()

    with open(os.path.join(repository, "Deploy.yaml")) as f:
        config = yaml.load(f)

    click.echo("config: %r" % config)

    tag = "%s/%s" % (obj.get("build_org"), basename)
    name = "mydeploy_%s" % basename
    session = obj.get("db")

    # find old running container
    echo("Looking for running containers")
    running_containers = []
    for check in docker.containers():
        if check.get("Image") == "%s:latest" % tag:
            click.echo("Found %s (%s)" % (check.get("Id"), check.get("Status")))
            running_containers.append(check.get("Id"))
    if not len(running_containers):
        click.echo("non found.")

    # build docker
    echo('Building Dockerfile')
    buildout = docker.build(path=repository, tag=tag, quiet=True, nocache=True, rm=True, stream=True)

    for l in buildout:
        row = json.loads(l)
        if row.get("stream"):
            click.echo("   " + row["stream"].strip())
            del row["stream"]
        if len(row):
            click.echo("%r" % row)

    # create container
    echo("Creating Docker Container")

    container = docker.create_container(tag,
                                        detach=True,
                                        ports=config.get("ports"),
                                        environment=config.get("environment"),
                                        name=config.get("name"))
    click.echo("container %r" % container)
    container_id = container.get("Id")
    dbcontainer = DbContainer(container_id=container_id, image=tag, config=json.dumps(config))
    session.add(dbcontainer)
    session.commit()

    echo("Configuring Stuff")
    info = docker.inspect_image(tag)
    binds = {}
    volumes = info.get("ContainerConfig").get("Volumes")
    for vol in volumes:
        vpath = os.path.join(os.getcwd(), "VOLUMES", vol[1:])
        os.makedirs(vpath, exist_ok=True)
        binds[vpath] = {
            'bind': vol,
            'ro': False
        }
    click.echo("Binds %r" % binds)

    # stopping old containers
    if len(running_containers):
        echo("Stopping old containers")
        for cont in running_containers:
            dbcontainer = session.query(DbContainer).get(cont)
            if dbcontainer:
                session.delete(dbcontainer)
            res = docker.stop(cont)

    # start container
    echo("Starting Container")

    start = docker.start(container_id, publish_all_ports=False, binds=binds)
    click.echo(start)

    click.echo(os.getcwd())

    if nginx:
        echo("writing nginx config file and reloading nginx")
        nginx.write(create_nginx_config(session, docker))
        subprocess.call(["sudo", "--non-interactive", "reload_nginx"])


if __name__ == '__main__':
    cli(obj={})
