# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "confluent-kafka",
# ]
# ///
"""
Consume messages from Kafka topics for testing.

Supports both plain (no auth) and mTLS modes:

  # Plain — consume from 'metric' topic on port 9092
  uv run consumer.py

  # mTLS — consume from 'portfolio-wallet-events' on port 9093
  uv run consumer.py --mtls \
    --bootstrap-server core-kafka-bootstrap.kafka.svc:9093 \
    --topic portfolio-wallet-events \
    --group-id portfolio-test-group \
    --ca-cert /certs/ca.crt \
    --user-cert /certs/user.crt \
    --user-key /certs/user.key
"""

import argparse
import json
import signal
import sys

from confluent_kafka import Consumer, KafkaError

running = True


def shutdown(signum, frame):
    global running
    running = False


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    parser = argparse.ArgumentParser(description="Kafka test consumer")
    parser.add_argument(
        "--bootstrap-server",
        default="core-kafka-bootstrap.kafka.svc:9092",
    )
    parser.add_argument("--topic", default="metric")
    parser.add_argument("--group-id", default="test-consumer-group")
    parser.add_argument("--mtls", action="store_true", help="Enable mTLS")
    parser.add_argument("--ca-cert", help="Path to cluster CA certificate")
    parser.add_argument("--user-cert", help="Path to user certificate")
    parser.add_argument("--user-key", help="Path to user private key")
    args = parser.parse_args()

    conf = {
        "bootstrap.servers": args.bootstrap_server,
        "group.id": args.group_id,
        "auto.offset.reset": "earliest",
    }

    if args.mtls:
        conf.update(
            {
                "security.protocol": "SSL",
                "ssl.ca.location": args.ca_cert,
                "ssl.certificate.location": args.user_cert,
                "ssl.key.location": args.user_key,
            }
        )

    consumer = Consumer(conf)
    consumer.subscribe([args.topic])
    print(f"subscribed to '{args.topic}', waiting for messages (ctrl+c to stop)...")

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"reached end of {msg.topic()} [{msg.partition()}]")
                else:
                    print(f"error: {msg.error()}", file=sys.stderr)
                continue

            payload = json.loads(msg.value().decode())
            print(
                f"[{msg.topic()}:{msg.partition()}@{msg.offset()}] "
                f"key={msg.key().decode()} value={json.dumps(payload, indent=2)}"
            )
    finally:
        consumer.close()
        print("consumer closed")


if __name__ == "__main__":
    main()
