# Strimzi Kafka Cluster

A KRaft-mode Kafka cluster managed by the [Strimzi operator](https://strimzi.io/) with two listeners:
a plain (unauthenticated) listener and a TLS listener with mTLS authentication and ACL-based authorization.

## Architecture

### Listeners

| Name | Port | Protocol | Authentication | Use case |
|------|------|----------|----------------|----------|
| `plain` | 9092 | PLAINTEXT | None | Open access to topics without ACLs |
| `tls` | 9093 | SSL | mTLS (client certificates) | Restricted access with per-user ACLs |

### Authorization model

Authorization is set to `simple` (Kafka ACLs) with `allow.everyone.if.no.acl.found: true`.
This means:

- **Topics with no ACLs** (e.g. `metric`) are open to everyone, including unauthenticated clients
  on the plain listener.
- **Topics with ACLs** (e.g. `portfolio-wallet-events`, `portfolio-wallet-checkpoint`) block
  unauthenticated clients. Only mTLS users with matching ACLs can access them.

This avoids the need for `ANONYMOUS` as a superUser (which would bypass all ACLs) and does not
require manually created ACLs (which the Strimzi User Operator would delete on reconciliation).

### Why this approach

Strimzi's User Operator treats `KafkaUser` custom resources as the single source of truth for ACLs.
Any ACLs created manually (e.g. via `kafka-acls.sh`) are deleted on the next reconciliation cycle.
This rules out managing `User:ANONYMOUS` ACLs out-of-band.

The alternatives considered:

| Approach | Drawback |
|----------|----------|
| `superUsers: [ANONYMOUS]` | Bypasses all ACLs, no topic isolation |
| Manual ACLs for `User:ANONYMOUS` | Wiped by User Operator on reconciliation |
| SCRAM-SHA-512 on plain listener | Requires credentials for all clients, even for open topics |
| `allow.everyone.if.no.acl.found: true` | Topics without ACLs are fully open (acceptable trade-off) |

The chosen approach (`allow.everyone.if.no.acl.found`) gives the best balance: open topics stay open,
protected topics are enforced by Strimzi-managed ACLs, and no manual intervention is needed.

### Topics

| Topic | Partitions | Cleanup | ACLs | Access |
|-------|-----------|---------|------|--------|
| `metric` | 3 | delete (24h retention) | None | Open to all via plain listener |
| `portfolio-wallet-events` | 3 | delete (7d retention) | Yes | mTLS only |
| `portfolio-wallet-checkpoint` | 1 | compact | Yes | mTLS only |

### Users

| User | Authentication | Permissions |
|------|---------------|-------------|
| `core-portfolio-producer` | mTLS | Write to `portfolio-wallet-events`, Read/Write to `portfolio-wallet-checkpoint` |
| `portfolio-consumer` | mTLS | Read from `portfolio-wallet-events` and `portfolio-wallet-checkpoint`, consumer groups prefixed `portfolio-` |

## Deployment

```bash
# Install the Strimzi operator first (see ../strimzi-operator/)
# Then deploy the Kafka cluster:
just install

# Check status:
just status

# View user secrets:
just secrets
```

## Running tests

All tests run from a broker pod using the built-in Kafka CLI tools. No external dependencies needed.

### Plain listener tests

```bash
# Produce to 'metric' (open topic, should succeed)
kubectl exec -n kafka core-broker-0 -- bash -c '
  echo "{\"test\":\"plain-metric\"}" \
  | /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9092 \
    --topic metric'

# Consume from 'metric' (should succeed)
kubectl exec -n kafka core-broker-0 -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9092 \
    --topic metric --from-beginning --timeout-ms 10000

# Produce to 'portfolio-wallet-events' (protected topic, should DENY)
kubectl exec -n kafka core-broker-0 -- bash -c '
  echo "{\"test\":\"should-fail\"}" \
  | /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9092 \
    --topic portfolio-wallet-events'
# Expected: TopicAuthorizationException
```

### mTLS listener tests

First, extract the certificates and create keystores:

```bash
# Extract certs
mkdir -p /tmp/kafka-mtls-test && cd /tmp/kafka-mtls-test

# Cluster CA (for trusting the broker)
kubectl get secret core-cluster-ca-cert -n kafka \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > cluster-ca.crt

# Producer user certs
kubectl get secret core-portfolio-producer -n kafka \
  -o jsonpath='{.data.user\.crt}' | base64 -d > producer-user.crt
kubectl get secret core-portfolio-producer -n kafka \
  -o jsonpath='{.data.user\.key}' | base64 -d > producer-user.key

# Consumer user certs
kubectl get secret portfolio-consumer -n kafka \
  -o jsonpath='{.data.user\.crt}' | base64 -d > consumer-user.crt
kubectl get secret portfolio-consumer -n kafka \
  -o jsonpath='{.data.user\.key}' | base64 -d > consumer-user.key

# Create PKCS12 keystores
openssl pkcs12 -export -in producer-user.crt -inkey producer-user.key \
  -out producer-keystore.p12 -name producer -password pass:changeit
openssl pkcs12 -export -in consumer-user.crt -inkey consumer-user.key \
  -out consumer-keystore.p12 -name consumer -password pass:changeit
keytool -import -trustcacerts -alias cluster-ca -file cluster-ca.crt \
  -keystore truststore.p12 -storetype PKCS12 -storepass changeit -noprompt
```

> Note: the truststore must contain the **cluster CA** (`core-cluster-ca-cert`), not the clients CA.
> The cluster CA signs the broker certificates; the clients CA signs user certificates.

Copy keystores and create configs on the broker pod:

```bash
kubectl cp /tmp/kafka-mtls-test/truststore.p12 kafka/core-broker-0:/tmp/truststore.p12
kubectl cp /tmp/kafka-mtls-test/producer-keystore.p12 kafka/core-broker-0:/tmp/producer-keystore.p12
kubectl cp /tmp/kafka-mtls-test/consumer-keystore.p12 kafka/core-broker-0:/tmp/consumer-keystore.p12

kubectl exec -n kafka core-broker-0 -- bash -c '
cat > /tmp/producer.properties <<EOF
security.protocol=SSL
ssl.truststore.location=/tmp/truststore.p12
ssl.truststore.password=changeit
ssl.truststore.type=PKCS12
ssl.keystore.location=/tmp/producer-keystore.p12
ssl.keystore.password=changeit
ssl.keystore.type=PKCS12
EOF

cat > /tmp/consumer.properties <<EOF
security.protocol=SSL
ssl.truststore.location=/tmp/truststore.p12
ssl.truststore.password=changeit
ssl.truststore.type=PKCS12
ssl.keystore.location=/tmp/consumer-keystore.p12
ssl.keystore.password=changeit
ssl.keystore.type=PKCS12
EOF'
```

Run the mTLS tests:

```bash
# mTLS produce to 'portfolio-wallet-events' as producer (should succeed)
kubectl exec -n kafka core-broker-0 -- bash -c '
  echo "{\"test\":\"mtls-produce\"}" \
  | /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --producer.config /tmp/producer.properties'

# mTLS consume from 'portfolio-wallet-events' as consumer (should succeed)
kubectl exec -n kafka core-broker-0 -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --consumer.config /tmp/consumer.properties \
    --group portfolio-test-group \
    --from-beginning --timeout-ms 10000

# mTLS consumer trying to PRODUCE (should DENY)
kubectl exec -n kafka core-broker-0 -- bash -c '
  echo "{\"test\":\"should-fail\"}" \
  | /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --producer.config /tmp/consumer.properties'
# Expected: TopicAuthorizationException

# mTLS producer trying to CONSUME (should DENY)
kubectl exec -n kafka core-broker-0 -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --consumer.config /tmp/producer.properties \
    --group portfolio-sneaky-group \
    --from-beginning --timeout-ms 10000
# Expected: GroupAuthorizationException
```

## Test report (2026-04-12)

| # | Test | Listener | Expected | Result |
|---|------|----------|----------|--------|
| 1 | Plain produce to `metric` | 9092 | Allowed | Allowed |
| 2 | Plain produce to `portfolio-wallet-events` | 9092 | Denied | Denied (`TopicAuthorizationException`) |
| 3 | mTLS `core-portfolio-producer` produce to `portfolio-wallet-events` | 9093 | Allowed | Allowed |
| 4 | mTLS `portfolio-consumer` produce to `portfolio-wallet-events` | 9093 | Denied | Denied (`TopicAuthorizationException`) |
| 5 | mTLS `portfolio-consumer` consume from `portfolio-wallet-events` | 9093 | Allowed | Allowed (10 messages) |
| 6 | mTLS `core-portfolio-producer` consume from `portfolio-wallet-events` | 9093 | Denied | Denied (`GroupAuthorizationException`) |
| 7 | Unauthenticated produce to `portfolio-wallet-events` | 9092 | Denied | Denied (`TopicAuthorizationException`) |

## Files

| File | Description |
|------|-------------|
| `kafka.yaml` | Kafka cluster CR (listeners, authorization, config) |
| `broker.yaml` | Broker node pool |
| `controller.yaml` | Controller node pool |
| `topics.yaml` | KafkaTopic resources |
| `users.yaml` | KafkaUser resources (mTLS users with ACLs) |
| `producer.py` | Python test producer (plain and mTLS modes, requires `confluent-kafka`) |
| `consumer.py` | Python test consumer (plain and mTLS modes, requires `confluent-kafka`) |
| `justfile` | Deployment and test commands |
