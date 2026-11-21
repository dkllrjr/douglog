import click
from pathlib import Path
import tomllib
import os
import time
import re
import numpy as np
from glob import glob
import subprocess
from datetime import datetime
import importlib.metadata


#  ──────────────────────────────────────────────────────────────────────────
# global variables

douglog_version = importlib.metadata.version('douglog')
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)


#  ──────────────────────────────────────────────────────────────────────────
# global functions

def logbook_not_found(logbook):
    click.echo(logbook + ' logbook not found in config.')
    exit()


#  ──────────────────────────────────────────────────────────────────────────
# base command

# done for the config
@click.group(invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.version_option(douglog_version)
@click.option('-c', '--config', default='~/.config/dlog.toml', type=str, help="Config file path", show_default=True)
@click.pass_context
def dlog(ctx, config):
    """Simple and quick logging program."""

    ctx.ensure_object(dict)

    config = Path(config).expanduser()
    if config.exists():

        with open(config, 'rb') as file:
            toml = tomllib.load(file)

        # required config options
        required = ['logbooks']
        for option in required:
            if option not in toml:
                click.echo('Config requires "' + key + '" to be set.')
                exit()

        # home log directory
        if 'home' in toml:
            ctx.obj['home'] = Path(toml['home']).expanduser()
        else:
            ctx.obj['home'] = Path('~/dlogs').expanduser()

        # individual logs
        ctx.obj['logbooks'] = []
        for logbook in toml['logbooks']:
            ctx.obj['logbooks'].append(logbook)

            logbook_path = ctx.obj['home'] / Path(logbook)
            if not logbook_path.exists():
                os.mkdir(logbook_path)

        ctx.obj['logbooks'] = sorted(ctx.obj['logbooks'])

        # editor
        if 'editor' in toml:
            ctx.obj['editor'] = toml['editor']
        else:
            ctx.obj['editor'] = 'vim'

    else:
        click.echo('No config file, exiting.')
        exit()


#  ──────────────────────────────────────────────────────────────────────────
# log command to generate single logs

@dlog.command('log', short_help='Open a new log in your editor.',context_settings=CONTEXT_SETTINGS)
@click.argument('logbook', type=str)
@click.pass_context
def log(ctx, logbook):
    """Open a new log in LOGBOOK in your editor."""

    if logbook in ctx.obj['logbooks']:
        logbook_path = ctx.obj['home'] / Path(logbook)

        epoch = str(np.floor(time.time()).astype(np.int64))
        date = time.strftime("%a, %d %b %Y %H:%M:%S UTC", time.gmtime())

        file_path = logbook_path / Path(epoch + '.md')
        with open(file_path, 'a') as file:
            file.write('# ' + date + '\n')

        # editting 
        click.edit(filename=file_path, editor=ctx.obj['editor'])

        # committing 
        git_path = logbook + '/' + file_path.name
        ctx.invoke(git, git_commands=['add', git_path])
        ctx.invoke(git, git_commands=['commit', '-m', '"Added ' + git_path + '"'])

    else:
        logbook_not_found(logbook)


#  ──────────────────────────────────────────────────────────────────────────
# list command to list logs

@dlog.command(context_settings=CONTEXT_SETTINGS)
@click.option('-l', '--logs', default=False, help='List logs as well.', is_flag=True)
@click.pass_context
def list(ctx, logs):
    """Lists all logbooks."""

    for logbook in ctx.obj['logbooks']:
        click.echo(logbook)
        
        if logs:
            logbook_path = ctx.obj['home'] / Path(logbook)
            file_paths = sorted(logbook_path.glob('*.md'))

            for file_path in file_paths:

                date = datetime.utcfromtimestamp(int(file_path.stem)).isoformat()
                click.echo(file_path.name + ' : ' + date)

            click.echo()

    exit()


#  ──────────────────────────────────────────────────────────────────────────
# search command

@dlog.command('search', short_help='Searches through your logs. Records the first hit only.', context_settings=CONTEXT_SETTINGS)
@click.option('-l', '--logbook', type=str, help="Specified logbook to search.", default=None)
@click.option('-pm', '--plus-minus', 'plusminus', type=str, help="Lines above (minus) and below (plus) to show: e.g. +plus-minus or -minus+plus.", default=None)
@click.option('--case', 'case', help="Allows for search with case sensitive REGEX.", default=False, is_flag=True)
@click.option('-e', '--edit', type=int, help="Opens the specified file from the result list in the editor: e.g. -e 1", default=0)
@click.option('-c', '--cat', type=int, help="Displays the text of the specified file from the result list to the terminal (cat-ing): e.g. -c 1", default=0)
@click.argument('regex', type=str)
@click.pass_context
def search(ctx, logbook, plusminus, case, edit, cat, regex):
    """
    Searches through your logs for the given REGEX. Searches through all logs unless one is specified. Results are printed as:

    [result #] logbook: filename: date: line number +plus -minus:
    line(s)
    """

    def inbook(ctx, logbook, plusminus, case, edit, cat, regex, result):

        logbook_path = ctx.obj['home'] / Path(logbook)
        file_paths = sorted(logbook_path.glob('*.md'))

        hit = False

        for j, file_path in enumerate(file_paths):

            date = datetime.utcfromtimestamp(int(file_path.stem)).isoformat()

            with click.open_file(file_path, 'r') as file:

                lines = file.readlines()
                for i, line in enumerate(lines):

                    if not case: # for case sensitive regex
                        regex = regex.lower()
                        search_line = line.lower()

                    else:
                        search_line = line

                    # match = re.search(regex, search_line)
                    match_iter = re.finditer(regex, search_line)

                    matches = []
                    for match in match_iter:
                        matches.append(match)

                    if len(matches) > 0:

                        hit = True

                        found_line = '[' + str(result) + '] ' + logbook + ': ' + file_path.stem + ': ' + date + ': ' + str(i + 1)

                        if plusminus is not None: # getting lines above and below hit

                            plus, minus = interpret_plusminus(plusminus)
                            if plus > 0:
                                found_line += '+' + str(plus)
                            if minus > 0:
                                found_line += '-' + str(minus)

                            found_line += ':'
                            click.echo(click.style(found_line, bold=True))

                            for l in lines[i-minus:i+plus+1]:

                                if l is line:
                                    click.echo(click.style(l.strip('\n'), fg='blue'))
                                else:
                                    click.echo(l.strip('\n'))


                        elif edit == result: # opening specified result in editor
                            click.edit(filename=file_path, editor=ctx.obj['editor'])
                            ctx.exit()

                        elif cat == result: # cat-ing specified result file to the terminal
                            click.echo(''.join(lines))
                            ctx.exit()

                        elif not cat:
                            click.echo(click.style(found_line, bold=True))

                            # echoing hits with blinking
                            for m, _ in enumerate(matches):
                                if m == 0:
                                    line_w_matches = line[0:matches[m].span()[0]] + click.style(line[matches[m].span()[0]:matches[m].span()[1]], blink=True, fg='red')
                                else:
                                    line_w_matches += line[matches[m-1].span()[1]:matches[m].span()[0]] + click.style(line[matches[m].span()[0]:matches[m].span()[1]], blink=True, fg='red')

                            line_w_matches += line[matches[-1].span()[1]::]
                            click.echo(line_w_matches.strip('\n'))

                        result += 1

        return result, hit

    
    def interpret_plusminus(plusminus):

        def _get_indices(plusminus, plus=True):

            symbols = ['+', '-']

            if not plus:
                symbols = symbols[::-1]

            if symbols[0] in plusminus:

                if symbols[1] in plusminus:

                    if plusminus.find(symbols[0]) < plusminus.find(symbols[1]):
                        return slice(plusminus.find(symbols[0]), plusminus.find(symbols[1]))
                    else:
                        return slice(plusminus.find(symbols[0]), None)

                else:
                    return slice(plusminus.find(symbols[0]), None)

            elif symbols[1] not in plusminus and plus: # assuming plus if no symbols are given
                return slice(None, None)

            else:
                return None


        plus_slice = _get_indices(plusminus)
        minus_slice = _get_indices(plusminus, plus=False)

        if plus_slice is not None:
            plus = abs(int(plusminus[plus_slice]))
        else:
            plus = 0

        if minus_slice is not None:
            minus = abs(int(plusminus[minus_slice]))
        else:
            minus = 0

        return plus, minus


    result = 1 # result hit counter

    if logbook:
        if logbook in ctx.obj['logbooks']:
            inbook(ctx, logbook, plusminus, case, edit, cat, regex, result)
        else:
            logbook_not_found(logbook)

    else:
        for logbook_i, logbook in enumerate(ctx.obj['logbooks']):
            result, hit = inbook(ctx, logbook, plusminus, case, edit, cat, regex, result)

            if logbook_i < len(ctx.obj['logbooks']) - 1 and hit and not cat:
                click.echo() # adding space between logbooks


#  ──────────────────────────────────────────────────────────────────────────
# git command

CONTEXT_SETTINGS_git = CONTEXT_SETTINGS.copy()
CONTEXT_SETTINGS_git['ignore_unknown_options'] = True

@dlog.command('git', short_help='Git manage the logbooks.', context_settings=CONTEXT_SETTINGS_git)
@click.argument('git_commands', type=click.UNPROCESSED, nargs=-1)
@click.pass_context
def git(ctx, git_commands):
    """Git command to manage the douglog git repository."""

    command = ['git', '-C', ctx.obj['home']]

    for arg in git_commands:
        command.append(arg)

    subprocess.run(command)


#  ──────────────────────────────────────────────────────────────────────────
# delete command

@dlog.command('delete', short_help='Delete a log.', context_settings=CONTEXT_SETTINGS)
@click.argument('logbook', type=str)
@click.option('-l', '--log', type=str, default=None, help='Delete specified log.')
@click.pass_context
def delete(ctx, logbook, log):
    """Delete a log from the LOGBOOK. Deletes the most recent log if none is specified."""

    if logbook in ctx.obj['logbooks']:
        logbook_path = ctx.obj['home'] / Path(logbook)
        file_paths = sorted(logbook_path.glob('*.md'))

        if log:
            log_path = logbook_path / Path(log)
            if log_path in file_paths:
                delete_log = log_path
            else:
                click.echo('Log specified but not found.')
                exit()
        else:
            delete_log = file_paths[-1]

        if click.confirm('Do you want to delete: ' + logbook + '/' + delete_log.name + '?'):
            click.echo('Deleting ' + delete_log.name + ' in ' + logbook)
            subprocess.run(['rm', delete_log])

            # committing 
            git_path = logbook + '/' + delete_log.name
            ctx.invoke(git, git_commands=['add', git_path])
            ctx.invoke(git, git_commands=['commit', '-m', '"Deleted ' + git_path + '"'])

    else:
        logbook_not_found(logbook)
