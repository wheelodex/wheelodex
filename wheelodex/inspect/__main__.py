import json
import sys
from   .inspect import inspect_wheel
from   ..util   import for_json

def main():
    for wheelfile in sys.argv[1:]:
        with open(wheelfile, 'rb') as fp:
            about = inspect_wheel(fp)
            print(json.dumps(about, sort_keys=True, indent=4, default=for_json))

if __name__ == '__main__':
    main()
