#!/usr/bin/env bash
type=report
if [[ $1 == html ]]; then
    type=html
fi
python -m coverage "$type"
