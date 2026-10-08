# ClamAV Installation on OpenShift

This guide installs ClamAV in the same OpenShift namespace as the application. Pods in the namespace can connect to it through the `clamav-gold` Kubernetes Service.

## Prerequisites

Install `oc`, `helm`, and `git`, then log in to the BC Gov OpenShift Silver cluster.

Select the target namespace:

```bash
oc project c72cba-test
```

## Install ClamAV

Clone the common ClamAV chart:

```bash
git clone https://github.com/bcgov/common-hosted-clamav-service.git
cd common-hosted-clamav-service
```

Create `clamav-gold-values.yaml`:

```yaml
global:
  imagePullSecrets: []

fullnameOverride: clamav-gold
replicaCount: 1

service:
  type: ClusterIP
  port: 3310

resources:
  requests:
    cpu: 300m
    memory: 2Gi
  limits:
    cpu: 1000m
    memory: 3Gi

persistentVolume:
  enabled: true
  size: 2Gi
  storageClass: netapp-block-standard

hpa:
  enabled: false
```

Install the chart:

```bash
helm upgrade --install clamav-gold ./helm/_clamav \
  --namespace c72cba-test \
  --values clamav-gold-values.yaml \
  --wait \
  --timeout 10m
```

## Verify the Installation

Confirm that the pod is ready and that the Service and persistent volume claim exist:

```bash
oc -n c72cba-test get pods
oc -n c72cba-test get service clamav-gold
oc -n c72cba-test get pvc
```

The ClamAV pod should report `Running` and `Ready`.

For a quick connectivity check, forward the service port:

```bash
oc -n c72cba-test port-forward service/clamav-gold 3310:3310
```

Keep that command running and execute this in another terminal:

```bash
printf 'zPING\0' | nc -w 5 127.0.0.1 3310
```

The expected response is:

```text
PONG
```

## Application Configuration

Applications in the same namespace connect through the Kubernetes Service name:

```ini
CLAMAV_HOST=clamav-gold
CLAMAV_PORT=3310
```

Use the corresponding namespace in the commands when installing into development or production.
