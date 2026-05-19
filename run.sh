#!/bin/bash

python app.py &
sleep 2
ngrok http 5050
