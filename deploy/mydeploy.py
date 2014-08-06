#!/usr/bin/env python3
import click

@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx,debug):
    ctx.obj['debug'] = debug
    click.echo('Debug mode is %s' % ('on' if debug else 'off'))

@cli.command()
@click.pass_obj
def sync(obj):
    click.echo('Synching %r'% str(ctx))

if __name__ == '__main__':
    cli(obj={})