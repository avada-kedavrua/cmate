# import argparse


# parser = argparse.ArgumentParser()

# parser.add_argument('-c', '--config', nargs='+', dest='cfg_pths', required=True)
# parser.add_argument('-r', '--rule', nargs='+', dest='rule_pths', required=True)

# args = parser.parse_args()

# for cfg_pth in args.cfg_pths:
#     if ':' in cfg_pth:


import json


with open('./test.json') as f:
    data = json.load(f)


class JsonPath:
    def __init__(self, pth: str):
        self._raw_pth = pth

    @property
    def namespace(self):
        breakpoint()

    @property
    def parent(self):
        breakpoint()


expr = "${spec.containers[0].env[!].name} == 'MINDIE_MS_P_RATE'"
JsonPath('spec.containers[0].env[!].name')
BinOp('=')
Str('MINDIE_MS_P_RATE')
