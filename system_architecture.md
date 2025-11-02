# System Architecture Diagram

## Recording Flow

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant WS as WebSocket Server
    participant DB as Database
    participant FS as File System
    participant PS as Pose Streamer

    UI->>WS: Start recording (session metadata)
    WS->>DB: Create SessionRecording
    DB-->>WS: Session ID
    WS-->>UI: Session created

    loop Recording Loop
        PS->>WS: Pose data + video frame
        WS->>FS: Store video frame
        WS->>DB: Store SessionFrame with pose data
        WS->>UI: Recording status update
    end

    UI->>WS: Stop recording
    WS->>DB: Update SessionRecording (completed)
    WS-->>UI: Recording finalized
```

## Replay Flow

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant WS as WebSocket Server
    participant DB as Database
    participant FS as File System
    participant CAM as Live Camera

    UI->>WS: Connect to replay (session ID)
    WS->>DB: Fetch session frames
    DB-->>WS: Frame data

    UI->>CAM: Start live camera feed
    CAM-->>UI: Live video stream

    loop Playback Loop
        WS->>UI: Send frame data (pose + timestamp)
        UI->>UI: Overlay pose on live video
    end

    UI->>WS: Playback control (play/pause/seek)
    WS-->>UI: Adjust frame sequence
```

## Component Architecture

```mermaid
graph TB
    subgraph "Frontend"
        A[pose_realtime.html] --> B[Recording Controls]
        A --> C[Live Pose Display]
        D[session_replay.html] --> E[Replay Controls]
        D --> F[Webcam + Pose Overlay]
        G[session_list.html] --> H[Session Management]
    end

    subgraph "Backend"
        I[PoseConsumer] --> J[Recording Handler]
        I --> K[Live Pose Streamer]
        L[SessionReplayConsumer] --> M[Frame Streamer]
        N[Session Views] --> O[CRUD Operations]
        P[Models] --> Q[SessionRecording]
        P --> R[SessionFrame]
    end

    subgraph "Storage"
        S[(Database)]
        T[Media Files]
    end

    A -.-> I
    D -.-> L
    G -.-> N
    J -.-> Q
    J -.-> R
    M -.-> Q
    M -.-> R
    N -.-> Q
    Q -.-> S
    R -.-> S
    J -.-> T
```

## Database Schema

```mermaid
erDiagram
    User ||--o{ SessionRecording : creates
    SessionRecording ||--o{ SessionFrame : contains
    
    User {
        int id PK
        string username
        string email
        string password
    }
    
    SessionRecording {
        uuid id PK
        string name
        text description
        datetime created_at
        int duration
        int frame_count
        int user_id FK
        string video_file_path
        string status
    }
    
    SessionFrame {
        int id PK
        uuid session_id FK
        float timestamp
        int frame_number
        json pose_data
        string image_path
    }