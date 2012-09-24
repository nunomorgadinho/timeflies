#!/usr/bin/python3

import re
import os
import sys
from datetime import date

sys.path.append('../src') 

from timeflies import main

last_arg = sys.argv[-1]
path_prefix, rest = last_arg.split('/', 1)
path_prefix = ' ' + path_prefix + '/'

arg_string = re.sub(path_prefix, ' ', ' ' + ' '.join(sys.argv[1:]))

print('% autogenerated: ' + ' '.join(sys.argv))
print('\\begin{inputfile}')
print('> timeflies.pl' + arg_string)
main(sys.argv)
print('\\end{inputfile}')

exit(0)
