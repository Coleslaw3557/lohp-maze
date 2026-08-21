"""Exercise the Gate node's two-bank game over its ESPHome API and assert the
right effects hit the server. Four paths against the 2026-08-21 series-bank
inputs (press_bank; the old per-pad press_pad build is dead — a lone pad
can't close a series bank, so the single-pad path left with it):
bank2-first fail, bank1 chime, bank1->bank2 chime, stage-expiry fail (waits
out the 30s window, so a full run takes ~1 minute).

Bench tool, not part of the standing suite — needs the sim server up AND the
gate node running first:  sim/esphome/run_node.sh gate -d  (API on :6063)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'esphome'))
from aioesphomeapi import APIClient  # noqa: E402

LOG = os.path.join(os.path.dirname(__file__), '..', 'sim.log')


def log_tail():
    with open(LOG) as f:
        return f.read()


async def press(cli, services, banks, gap=0.05):
    svc = next(s for s in services if s.name == 'press_bank')
    for b in banks:
        await cli.execute_service(svc, {'bank': b})
        await asyncio.sleep(gap)


async def main():
    fails = []
    cli = APIClient('127.0.0.1', 6063, None)
    await cli.connect(login=True)
    services = (await cli.list_entities_services())[1]

    async def round_(label, banks, expect, expect_absent=None, settle=3.0):
        mark = len(log_tail())
        await press(cli, services, banks)
        await asyncio.sleep(settle)
        got = log_tail()[mark:]
        ok = expect in got and (expect_absent is None or expect_absent not in got)
        print(('PASS  ' if ok else 'FAIL  ') + label)
        if not ok:
            fails.append(label)
            print('   log slice:', [l for l in got.splitlines() if 'Gate' in l][-4:])

    # bank 2 with no stage armed -> WrongAnswer
    await round_('bank2 first -> WrongAnswer', [2],
                 "Applying effect 'WrongAnswer' to room 'Gate'", settle=4)
    # bank 1 closure -> CorrectAnswer chime (stage armed)
    await round_('bank1 -> CorrectAnswer chime', [1],
                 "Applying effect 'CorrectAnswer' to room 'Gate'", settle=5)
    # bank 2 while staged -> second CorrectAnswer chime
    await round_('bank2 after bank1 -> CorrectAnswer chime', [2],
                 "Applying effect 'CorrectAnswer' to room 'Gate'", settle=5)
    # bank 1 again, then let the 30s stage window lapse -> bank 2 fails
    await press(cli, services, [1])
    print('      (waiting out the 30s stage window...)')
    await asyncio.sleep(31)
    await round_('bank2 after stage expiry -> WrongAnswer', [2],
                 "Applying effect 'WrongAnswer' to room 'Gate'", settle=4)

    await cli.disconnect()
    print('ALL PASS' if not fails else f'FAILURES: {fails}')
    return 0 if not fails else 1


raise SystemExit(asyncio.run(main()))
