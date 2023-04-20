#!/bin/sh
#setcap 'cap_net_bind_service=+ep cap_sys_boot+ep' /usr/bin/python3.8
cd /home/odroid
sleep 2
./OpenVPN/disconnect.sh
sleep 2
# checking internet connection
ping www.destin.be -c 1 -w 10
if [ $? -gt 0 ]
then
   echo NO INTERNET ?
else
   _HOST=$(hostname) || true
   if [ "$_IP" ];
   then
     printf "OVPN Host is %s\n" "$_HOST"
     openvpn3 session-start --config $_HOST.ovpn
     sleep 2
   fi
   _IP=$(hostname -I) || true
   if [ "$_IP" ];
   then
      printf "My IP address is %s\n" "$_IP"
      # signal that pasteurizer is up and running ?
   fi
fi
cd /etc/xrdp
setxkbmap -layout be
cd /home/odroid/Pasteurizer
/usr/bin/python3.8 PastoWeb.py 80
