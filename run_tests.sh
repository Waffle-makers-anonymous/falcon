#!/bin/bash
# Script to run falcon tests

export FALCON_TESTING=1
pytest tests/ "$@"
