"""Exercise the Gate node's two-bank game over its ESPHome API and assert the
right effects hit the server (four paths: bank2-first fail, bank1 chime,
bank1->bank2 complete, single-pad no-fire).

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


async def press(cli, services, pads, gap=0.05):
    svc = next(s for s in services if s.name == 'press_pad')
    for p in pads:
        await cli.execute_service(svc, {'pad': p})
        await asyncio.sleep(gap)


async def main():
    fails = []
    cli = APIClient('127.0.0.1', 6063, None)
    await cli.connect(login=True)
    services = (await cli.list_entities_services())[1]

    async def round_(label, pads, expect, expect_absent=None, settle=3.0):
        mark = len(log_tail())
        await press(cli, services, pads)
        await asyncio.sleep(settle)
        got = log_tail()[mark:]
        ok = expect in got and (expect_absent is None or expect_absent not in got)
        print(('PASS  ' if ok else 'FAIL  ') + label)
        if not ok:
            fails.append(label)
            print('   log slice:', [l for l in got.splitlines() if 'Gate' in l][-4:])

    # bank 2 with no stage armed -> WrongAnswer
    await round_('bank2 first -> WrongAnswer', [4, 5, 6],
                 "Applying effect 'WrongAnswer' to room 'Gate'", settle=4)
    # bank 1 simultaneous -> CorrectAnswer chime
    await round_('bank1 x3 -> CorrectAnswer chime', [1, 2, 3],
                 "Applying effect 'CorrectAnswer' to room 'Gate'", settle=5)
    # bank 2 while staged -> GateInspection complete
    await round_('bank2 after bank1 -> GateInspection', [4, 5, 6],
                 "Applying effect 'GateInspection' to room 'Gate'", settle=8)
    # a single pad press must NOT resolve a bank
    await round_('single pad -> nothing fires', [2],
                 '', expect_absent="to room 'Gate'", settle=3)

    await cli.disconnect()
    print('ALL PASS' if not fails else f'FAILURES: {fails}')
    return 0 if not fails else 1


raise SystemExit(asyncio.run(main()))
