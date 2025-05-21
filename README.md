```mermaid
flowchart LR
    A[Cognito Authenticated User]:::client
    B[Cognito User Pool]:::cognito
    C[API Gateway /logs]:::apigateway
    D[Lambda Log Ingest]:::lambda
    E[Lambda Log Retrieve]:::lambda
    F[DynamoDB Table]:::dynamodb
    G[KMS Key]:::kms

    A -->|Authenticate| B
    B -->|Return JWT Token| A
    A -->|JWT Token, HTTPS| C
    C -->|Validate JWT| B
    C -->|POST /logs| D
    C -->|GET /logs| E
    D -->|PutItem| F
    E -->|Query Last 100| F
    F -->|Encrypted with| G

    classDef client fill:#ECEFF1,stroke:#455A64,stroke-width:2px
    classDef cognito fill:#FF6F61,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef apigateway fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef lambda fill:#00A1E4,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef dynamodb fill:#4051B5,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef kms fill:#D13212,stroke:#232F3E,stroke-width:2px,color:#fff
