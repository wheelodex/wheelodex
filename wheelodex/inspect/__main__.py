import json
import sys
from   .inspect import inspect_wheel

def main():
    for wheelfile in sys.argv[1:]:
        about = inspect_wheel(wheelfile)
        print(json.dumps(about, sort_keys=True, indent=4))

if __name__ == '__main__':
    main()
