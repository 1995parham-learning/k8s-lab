# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "confluent-kafka",
# ]
# ///
"""
Produce messages to Kafka topics for testing.

Supports both plain (no auth) and mTLS modes:

  # Plain — produce to 'metric' topic on port 9092
  uv run producer.py

  # mTLS — produce to 'portfolio-wallet-events' on port 9093
  uv run producer.py --mtls \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --ca-cert /certs/ca.crt \
    --user-cert /certs/user.crt \
    --user-key /certs/user.key
"""

import argparse
import json
import time
import uuid

from confluent_kafka import Producer


def delivery_report(err, msg):
    if err is not None:
        print(f"delivery failed: {err}")
    else:
        print(
            f"delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}"
        )


def main():
    parser = argparse.ArgumentParser(description="Kafka test producer")
    parser.add_argument(
        "--bootstrap-server",
        default="core-kafka-bootstrap.kafka.svc:9092",
    )
    parser.add_argument("--topic", default="metric")
    parser.add_argument("--mtls", action="store_true", help="Enable mTLS")
    parser.add_argument("--ca-cert", help="Path to cluster CA certificate")
    parser.add_argument("--user-cert", help="Path to user certificate")
    parser.add_argument("--user-key", help="Path to user private key")
    parser.add_argument(
        "--count", type=int, default=10, help="Number of messages to send"
    )
    args = parser.parse_args()

    conf = {"bootstrap.servers": args.bootstrap_server}

    if args.mtls:
        conf.update(
            {
                "security.protocol": "SSL",
                "ssl.ca.location": args.ca_cert,
                "ssl.certificate.location": args.user_cert,
                "ssl.key.location": args.user_key,
            }
        )

    producer = Producer(conf)

    for i in range(args.count):
        payload = {
            "id": str(uuid.uuid4()),
            "index": i,
            "value": round(42.0 + i * 1.5, 2),
            "ts": time.time(),
        }
        producer.produce(
            args.topic,
            key=str(i),
            value=json.dumps(payload),
            callback=delivery_report,
        )
        producer.poll(0)
        print(f"sent message {i}")
        time.sleep(0.5)

    producer.flush()
    print("all messages flushed")


if __name__ == "__main__":
    main()
