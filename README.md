# ospf2zabbix
A collection of simple tools written in Python to interact with Zabbix.
<p align="center">
  <img height="200px" src="https://github.com/WillNilges/ospf2zabbix/assets/42927786/2eeb2ddd-2bb0-43c5-a7ab-528b8fff741d" alt="O2Z icon">
</p>

## Current Tools
- Retrieve OSPF data from the OSPF Explorer and automatically enroll nodes based on popularity
- Query a Zabbix instance's database to get a list of the noisiest triggers (A funtionality coming in 7.0)
  - Publish said list to S3
  - Publish said list to a Slack channel

## Deployment

For some reason, I decided to containerize this.

Clone the repo:

```
cd /usr/bin
git clone https://github.com/willnilges/ospf2zabbix
```

Fill out the .env file:

```
cp .env.sample .env
vim .env
```

Build the container like this:

```
docker build . --tag o2z
```

Then add a line to your crontab that looks like this:

```
0 0 * * 5 docker run --rm --env-file /usr/bin/ospf2zabbix/.env --name o2z-noisy-publish o2z >> /var/log/o2z.log
```

