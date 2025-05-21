```mermaid
graph TD
    A[Client] -->|Authenticate| B[AWS Cognito]
    A -->|POST /logs| C[API Gateway]
    A -->|GET /logs| C
    C -->|Validate JWT| B
    C -->|POST| D[Lambda: Log Entry]
    C -->|GET| E[Lambda: Log Retrieval]
    D --> F[DynamoDB: LogTable]
    E --> F
    D --> G[CloudWatch Logs]
    E --> G
    H[GitHub Actions] -->|Deploy| I[Terraform]
    I --> C
    I --> D
    I --> E
    I --> F
    I --> B