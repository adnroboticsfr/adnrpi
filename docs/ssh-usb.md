# SSH via USB OTG

L'ADNRPi One expose son port OTG comme une interface réseau USB (gadget NCM). **Un seul câble** alimente la carte et donne accès SSH — sans Ethernet, sans WiFi.

## Connexion

1. Branche un câble USB entre le **port OTG** de l'ADNRPi et ton ordinateur
2. Configure l'interface réseau USB sur ton PC :

**Linux :**
```bash
sudo ip addr add 172.22.1.2/24 dev usb0
sudo ip link set usb0 up
```

**Windows :** L'interface apparaît comme "RNDIS/Ethernet Gadget" — assigne l'IP `172.22.1.2` manuellement (masque `255.255.255.0`).

**macOS :** L'interface apparaît automatiquement — assigne `172.22.1.2` dans les préférences réseau.

3. Connecte-toi :
```bash
ssh root@172.22.1.1
```

## Notes

- L'IP de la carte est toujours `172.22.1.1`
- Débrancher le câble coupe aussi l'alimentation
- Pour des workloads intensifs (overclock 1368 MHz), préfère une alimentation 5V/2A dédiée
