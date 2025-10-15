<<<<<<< HEAD
# Validator Service Architecture

## System Overview
```mermaid
graph TB
    subgraph "Client Layer"
        A[User/Client]
        B[Main API Server]
    end
    
    subgraph "AWS Infrastructure"
        C[ECS Fargate<br/>Validator Service]
        D[Application Load Balancer]
        E[S3 Bucket<br/>pkg-artifacts]
        F[DynamoDB<br/>packages table]
        G[DynamoDB<br/>downloads table]
    end
    
    A -->|1. Download Request| B
    B -->|2. Validate Package| D
    D -->|3. Forward Request| C
    C -->|4. Check Package Metadata| F
    C -->|5. Download Validator Script| E
    C -->|6. Execute Validation| C
    C -->|7. Log Result| G
    C -->|8. Return Validation Result| D
    D -->|9. Forward Response| B
    B -->|10. Allow/Deny Download| A
```

## Detailed Validation Flow
```mermaid
sequenceDiagram
    participant U as User
    participant API as Main API
    participant LB as Load Balancer
    participant VS as Validator Service
    participant DDB as DynamoDB
    participant S3 as S3 Bucket
    
    U->>API: POST /api/packages/{pkg}/{ver}/download
    API->>LB: POST /validate
    LB->>VS: Forward validation request
    
    VS->>DDB: Get package metadata
    DDB-->>VS: Package info (is_sensitive, allowed_groups)
    
    alt Package is sensitive
        VS->>VS: Check user groups vs required groups
        alt User has access
            VS->>S3: Get validator script
            S3-->>VS: validator.js content
            VS->>VS: Execute validator script
            VS->>DDB: Log successful validation
        else User lacks access
            VS->>DDB: Log blocked access
            VS-->>LB: 403 Access Denied
        end
    else Package not sensitive
        VS->>DDB: Log allowed access
        VS-->>LB: 200 Validation OK
    end
    
    LB-->>API: Validation result
    API-->>U: Download URL or Error
```

## Data Models
```mermaid
erDiagram
    PACKAGES {
        string pkg_key PK
        string pkg_name
        string version
        boolean is_sensitive
        array allowed_groups
        string created_at
        string updated_at
    }
    
    DOWNLOADS {
        string event_id PK
        string pkg_name
        string version
        string user_id
        string timestamp
        string status
        string reason
        object validation_result
    }
    
    USERS {
        string user_id PK
        string username
        string password_hash
        array roles
        array groups
    }
    
    PACKAGES ||--o{ DOWNLOADS : "generates"
    USERS ||--o{ DOWNLOADS : "initiates"
```

## Security & Access Control
```mermaid
flowchart TD
    A[User Request] --> B{Authenticated?}
    B -->|No| C[Return 401]
    B -->|Yes| D{Token Valid?}
    D -->|No| E[Return 403]
    D -->|Yes| F{Package Sensitive?}
    F -->|No| G[Allow Download]
    F -->|Yes| H{User in Required Group?}
    H -->|No| I[Log & Block Access]
    H -->|Yes| J{Validator Script Exists?}
    J -->|No| K[Allow Download]
    J -->|Yes| L[Execute Validator]
    L --> M{Validation Passes?}
    M -->|No| N[Log & Block Access]
    M -->|Yes| O[Log & Allow Download]
    
    style C fill:#ffcccc
    style E fill:#ffcccc
    style I fill:#ffcccc
    style N fill:#ffcccc
    style G fill:#ccffcc
    style K fill:#ccffcc
    style O fill:#ccffcc
```

## Infrastructure Components
```mermaid
graph LR
    subgraph "ECS Cluster"
        A[Validator Service<br/>Node.js 22]
        B[Health Check<br/>/health endpoint]
    end
    
    subgraph "Networking"
        C[VPC<br/>10.0.0.0/16]
        D[Public Subnet<br/>10.0.1.0/24]
        E[Internet Gateway]
        F[Route Table]
    end
    
    subgraph "Load Balancing"
        G[Application Load Balancer]
        H[Target Group<br/>Port 3001]
    end
    
    subgraph "Monitoring"
        I[CloudWatch Logs<br/>/ecs/validator-service]
        J[ECS Service Metrics]
    end
    
    A --> B
    G --> H
    H --> A
    C --> D
    D --> E
    E --> F
    A --> I
    A --> J
```

## API Endpoints
```mermaid
graph TD
    A[Validator Service API] --> B[POST /validate]
    A --> C[GET /health]
    A --> D[GET /history/:userId]
    
    B --> E[Validate package access]
    B --> F[Execute custom validator]
    B --> G[Log validation result]
    
    C --> H[Service health check]
    
    D --> I[Get user validation history]
    D --> J[Query DynamoDB GSI]
```

## Error Handling & Logging
```mermaid
flowchart TD
    A[Validation Request] --> B{Input Valid?}
    B -->|No| C[Log Error<br/>Return 400]
    B -->|Yes| D{Package Exists?}
    D -->|No| E[Log Not Found<br/>Return 404]
    D -->|Yes| F{Access Allowed?}
    F -->|No| G[Log Access Denied<br/>Return 403]
    F -->|Yes| H{Validator Executes?}
    H -->|No| I[Log Validation Error<br/>Return 500]
    H -->|Yes| J[Log Success<br/>Return 200]
    
    C --> K[DynamoDB Downloads Table]
    E --> K
    G --> K
    I --> K
    J --> K
```
=======
# Validator Service Architecture

## System Overview
```mermaid
graph TB
    subgraph "Client Layer"
        A[User/Client]
        B[Main API Server]
    end
    
    subgraph "AWS Infrastructure"
        C[ECS Fargate<br/>Validator Service]
        D[Application Load Balancer]
        E[S3 Bucket<br/>pkg-artifacts]
        F[DynamoDB<br/>packages table]
        G[DynamoDB<br/>downloads table]
    end
    
    A -->|1. Download Request| B
    B -->|2. Validate Package| D
    D -->|3. Forward Request| C
    C -->|4. Check Package Metadata| F
    C -->|5. Download Validator Script| E
    C -->|6. Execute Validation| C
    C -->|7. Log Result| G
    C -->|8. Return Validation Result| D
    D -->|9. Forward Response| B
    B -->|10. Allow/Deny Download| A
```

## Detailed Validation Flow
```mermaid
sequenceDiagram
    participant U as User
    participant API as Main API
    participant LB as Load Balancer
    participant VS as Validator Service
    participant DDB as DynamoDB
    participant S3 as S3 Bucket
    
    U->>API: POST /api/packages/{pkg}/{ver}/download
    API->>LB: POST /validate
    LB->>VS: Forward validation request
    
    VS->>DDB: Get package metadata
    DDB-->>VS: Package info (is_sensitive, allowed_groups)
    
    alt Package is sensitive
        VS->>VS: Check user groups vs required groups
        alt User has access
            VS->>S3: Get validator script
            S3-->>VS: validator.py content
            VS->>VS: Execute validator script
            VS->>DDB: Log successful validation
        else User lacks access
            VS->>DDB: Log blocked access
            VS-->>LB: 403 Access Denied
        end
    else Package not sensitive
        VS->>DDB: Log allowed access
        VS-->>LB: 200 Validation OK
    end
    
    LB-->>API: Validation result
    API-->>U: Download URL or Error
```

## Data Models
```mermaid
erDiagram
    PACKAGES {
        string pkg_key PK
        string pkg_name
        string version
        boolean is_sensitive
        array allowed_groups
        string created_at
        string updated_at
    }
    
    DOWNLOADS {
        string event_id PK
        string pkg_name
        string version
        string user_id
        string timestamp
        string status
        string reason
        object validation_result
    }
    
    USERS {
        string user_id PK
        string username
        string password_hash
        array roles
        array groups
    }
    
    PACKAGES ||--o{ DOWNLOADS : "generates"
    USERS ||--o{ DOWNLOADS : "initiates"
```

## Security & Access Control
```mermaid
flowchart TD
    A[User Request] --> B{Authenticated?}
    B -->|No| C[Return 401]
    B -->|Yes| D{Token Valid?}
    D -->|No| E[Return 403]
    D -->|Yes| F{Package Sensitive?}
    F -->|No| G[Allow Download]
    F -->|Yes| H{User in Required Group?}
    H -->|No| I[Log & Block Access]
    H -->|Yes| J{Validator Script Exists?}
    J -->|No| K[Allow Download]
    J -->|Yes| L[Execute Validator]
    L --> M{Validation Passes?}
    M -->|No| N[Log & Block Access]
    M -->|Yes| O[Log & Allow Download]
    
    style C fill:#ffcccc
    style E fill:#ffcccc
    style I fill:#ffcccc
    style N fill:#ffcccc
    style G fill:#ccffcc
    style K fill:#ccffcc
    style O fill:#ccffcc
```

## Infrastructure Components
```mermaid
graph LR
    subgraph "ECS Cluster"
        A[Validator Service<br/>Node.js 22]
        B[Health Check<br/>/health endpoint]
    end
    
    subgraph "Networking"
        C[VPC<br/>10.0.0.0/16]
        D[Public Subnet<br/>10.0.1.0/24]
        E[Internet Gateway]
        F[Route Table]
    end
    
    subgraph "Load Balancing"
        G[Application Load Balancer]
        H[Target Group<br/>Port 3001]
    end
    
    subgraph "Monitoring"
        I[CloudWatch Logs<br/>/ecs/validator-service]
        J[ECS Service Metrics]
    end
    
    A --> B
    G --> H
    H --> A
    C --> D
    D --> E
    E --> F
    A --> I
    A --> J
```

## API Endpoints
```mermaid
graph TD
    A[Validator Service API] --> B[POST /validate]
    A --> C[GET /health]
    A --> D[GET /history/:userId]
    
    B --> E[Validate package access]
    B --> F[Execute custom validator]
    B --> G[Log validation result]
    
    C --> H[Service health check]
    
    D --> I[Get user validation history]
    D --> J[Query DynamoDB GSI]
```

## Error Handling & Logging
```mermaid
flowchart TD
    A[Validation Request] --> B{Input Valid?}
    B -->|No| C[Log Error<br/>Return 400]
    B -->|Yes| D{Package Exists?}
    D -->|No| E[Log Not Found<br/>Return 404]
    D -->|Yes| F{Access Allowed?}
    F -->|No| G[Log Access Denied<br/>Return 403]
    F -->|Yes| H{Validator Executes?}
    H -->|No| I[Log Validation Error<br/>Return 500]
    H -->|Yes| J[Log Success<br/>Return 200]
    
    C --> K[DynamoDB Downloads Table]
    E --> K
    G --> K
    I --> K
    J --> K
```
>>>>>>> c1c1f250728e8f0eb8736a4331c63be9084b0856
