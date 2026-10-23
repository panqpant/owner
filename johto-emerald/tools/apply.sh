#!/bin/sh
# Apply the Johto conversion to a clean pret/pokeemerald checkout: tools/apply.sh <pokeemerald dir>
set -e
here=$(dirname "$0")
python3 -I "$here/johto_trainers.py" "$1"
python3 -I "$here/johto_species.py" "$1"
python3 -I "$here/johto_wild.py" "$1"
python3 -I "$here/johto_text.py" "$1"
python3 -I "$here/johto_rewrap.py" "$1"
