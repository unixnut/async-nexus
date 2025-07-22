"""
Send a single event to the PULL listener on port 12346.
"""

from typing import Set, Dict, Sequence, Tuple, List, Union, AnyStr, Iterable, Callable, Generator, Type, Optional, TextIO, IO

import sys
import getopt
import asyncio
import random
import contextlib
import dataclasses
import logging

import zmq

import async_nexus



# *** DEFINITIONS ***
self = "zmq_send_event"



# *** FUNCTIONS ***
def show_help(dest=sys.stdout):
    print(__doc__.rstrip(), file=dest)


def report_error(msg):
    print(self + ": Error: " + msg, file=sys.stderr)


def report_warning(msg):
    print(self + ": Warning: " + msg, file=sys.stderr)


def report_notice(msg):
    print(self + ": Notice: " + msg, file=sys.stderr)


def do_send(socket: zmq.Socket, *, event_type: int, payload: str) -> None:
    id = random.randrange(2000,5000)
    event = async_nexus.Event(id, event_type, priority=1, payload=payload)
    logging.info("sending " + str(event))
    socket.send_json(event, default=dataclasses.asdict)


def main(argv: List[str]) -> int:
    # Note: not asyncio
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUSH)
    socket.connect('tcp://localhost:12346')

    if not argv[1:]:
        report_error("payload missing")
        return 1

    try:
        if argv[1] == "-t":
            t = argv[2]
        else:
            t = 996

        # payload is last argument
        ## socket.send_string("test (%s)!" % t)
        do_send(socket, event_type=t, payload=argv[-1])

    except ValueError:
        report_error("invalid type" + t)
        return 2

    except IndexError:
        report_error("arguments missing")
        return 1

    finally:
        socket.close(linger=2)
        ctx.term()



# *** MAINLINE ***
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv))
