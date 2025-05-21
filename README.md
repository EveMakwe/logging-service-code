graph TD
    subgraph Client
        A[Cognito Authenticated User]
    end
    subgraph AWS Cloud
        B[Cognito User Pool]
        C[API Gateway]
        D[Lambda Log Ingest]
        E[Lambda Log Retrieve]
        F[(DynamoDB Table)]
        G[KMS Key]
    end
    A-->|JWT Token|C
    C-->|Invoke (POST /logs)|D
    C-->|Invoke (GET /logs)|E
    D-->|PutItem|F
    E-->|Query (Last 100)|F
    F-->|Encryption|G
    C-->|Authorizer|B
