#!/bin/bash
set -e

echo "=== Testing hello_world.orm ==="
oromscript run examples/hello_world.orm

echo "=== Testing fibonacci.orm ==="
oromscript run examples/fibonacci.orm

echo "=== Testing classes.orm ==="
oromscript run examples/classes.orm

echo "=== Testing check command ==="
oromscript check examples/hello_world.orm

echo "=== Testing compile command ==="
oromscript compile examples/hello_world.orm --stdout

echo "=== All E2E tests passed successfully! ==="
