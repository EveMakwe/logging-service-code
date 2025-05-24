Serverless Log Service Application
Overview

This solution provides a fully serverless log management system with two core functions:

    Log Ingestion - Receives and stores log entries

    Log Retrieval - Returns the 100 most recent logs

 with AWS Lambda and deployed using Infrastructure-as-Code (Terraform).
Architecture

  # Serverless Log Service Architecture

┌────────────────────┐       [POST]       ┌────────────────────┐
│                    │───────────────────▶│                    │
│   Client           │                    │   API Gateway      │
│   Applications     │◀───────────────────│                    │
└────────────────────┘       [GET]        └─────────┬──────────┘
                                                    │
                                          ┌─────────▼──────────┐ 
                                          │                    │
                                          │    Lambda          │
                                          │    Functions       │
                                          │                    │
                                          └───────┬─────┬──────┘
                                                  │     │
                                        ╔═════════╝     ╚═════════╗
                                        ║                         ║
                                  ┌─────▼─────┐             ┌─────▼─────┐
                                  │           │             │           │
                                  │ log-      │             │ log-      │
                                  │ ingestion │             │ retrieval │
                                  │           │             │           │
                                  └─────┬─────┘             └─────┬─────┘
                                        │                         │
                                        ╚══════════╗     ╔════════╝
                                                   │     │
                                         ┌─────────▼─────▼──────────┐
                                         │                          │
                                         │       DynamoDB           │
                                         │     (Log Storage)        │
                                         │                          │
                                         └──────────────────────────┘

# Flow Directions:
# ────────────▶  Log Ingestion Path (Write)
# ◀────────────  Log Retrieval Path (Read)