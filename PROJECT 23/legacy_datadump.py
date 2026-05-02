import sys
import argparse

# FAULTY LOGIC: 
# 1. No help text for arguments.
# 2. Crashes with a raw traceback if the file is missing.
# 3. Uses print() for everything, making it hard to pipe data.
parser = argparse.ArgumentParser()
parser.add_argument("f") # What is 'f'? File? Format? Force?
parser.add_argument("d") # What is 'd'? Destination? Date?

args = parser.parse_args()

# If file 'f' doesn't exist, this throws a FileNotFoundError and exits.
data = open(args.f).read() 
print("Success") # Not helpful