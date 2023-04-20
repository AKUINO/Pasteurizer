#!/bin/sh
# Initialization of pull-ups for GPIO input pins linked to the Pasteurizer
# LOOK INTO hardConf.py !
gpio export 483 in
gpio export 476 out
gpio export 480 in
gpio export 477 out
gpio export 482 in
gpio export 432 out
gpio export 495 out
gpio -g mode 483 up
gpio -g write 476 0
gpio -g mode 480 up
gpio -g write 477 0
gpio -g mode 482 up
gpio -g write 432 0
gpio -g write 495 0
#echo 483 > /sys/class/gpio/export
## echo 476 > /sys/class/gpio/export
#echo 480 > /sys/class/gpio/export
## echo 477 > /sys/class/gpio/export
#echo 482 > /sys/class/gpio/export
## echo 432 > /sys/class/gpio/export
#echo 495 > /sys/class/gpio/export
#echo up > /sys/class/gpio/gpio483/pull
## echo down > /sys/class/gpio/gpio476/pull
## echo down > /sys/class/gpio/gpio477/pull
#echo up > /sys/class/gpio/gpio480/pull
#echo up > /sys/class/gpio/gpio482/pull
# echo down > /sys/class/gpio/gpio432/pull

setcap 'cap_net_bind_service=+ep cap_sys_boot+ep' /usr/bin/python3.8
su odroid --command "screen -d -m /home/odroid/Pasteurizer.sh"
