# senaiy-voice

A Pipecat AI voice agent built with a cascade pipeline (STT → LLM → TTS).

## Configuration

- **Bot Type**: Telephony
- **Transport(s)**: Twilio, SmallWebRTC
- **Pipeline**: Cascade
  - **STT**: OpenAI (Whisper)
  - **LLM**: OpenAI
  - **TTS**: OpenAI TTS
- **Features**:
  - Audio Recording
  - Transcription
  - Observability (Whisker + Tail)

## Setup

### Setting Up Twilio

#### 1. Create a TwiML Bin

A TwiML Bin tells Twilio how to handle incoming calls. You'll create one that establishes a WebSocket connection to your bot.

1. Go to the [Twilio Console](https://console.twilio.com)
2. Navigate to **TwiML Bins** → **My TwiML Bins**
3. Click the **+** to create a new TwiML Bin
4. Name your bin and add the TwiML:

    **For Local Development:**

    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Connect>
        <Stream url="wss://your-url.ngrok.io/ws" />
      </Connect>
    </Response>
    ```

    Replace `your-url.ngrok.io` with your ngrok URL.

    **For Pipecat Cloud:**

    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Connect>
        <Stream url="wss://api.pipecat.daily.co/ws/twilio">
          <Parameter name="_pipecatCloudServiceHost"
            value="AGENT_NAME.ORGANIZATION_NAME"/>
        </Stream>
      </Connect>
    </Response>
    ```

    Replace:
    - `AGENT_NAME` with the name of the agent you deployed to Pipecat Cloud
    - `ORGANIZATION_NAME` with the name of your Pipecat Cloud organization

5. Click **Save**

#### 2. Assign TwiML Bin to Your Phone Number

1. Navigate to **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your Twilio phone number
3. In the "Voice Configuration" section:
   - Set "A call comes in" to **TwiML Bin**
   - Select the TwiML Bin you created
4. Click **Save configuration**

### Server

1. **Navigate to server directory**:

   ```bash
   cd server
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run the bot**:

   **For local development:**
   - SmallWebRTC: `uv run bot.py`

   **For telephony deployment:**
   - Run ngrok: `ngrok http 7860`
   - Run bot:
     - Twilio: `uv run bot.py --transport twilio --proxy your_url.ngrok.io`

## Project Structure

```
senaiy-voice/
├── server/              # Python bot server
│   ├── bot.py           # Main bot implementation
│   ├── pyproject.toml   # Python dependencies
│   ├── .env.example     # Environment variables template
│   ├── .env             # Your API keys (git-ignored)
│   ├── Dockerfile       # Container image for Pipecat Cloud
│   └── pcc-deploy.toml  # Pipecat Cloud deployment config
├── .gitignore           # Git ignore patterns
└── README.md            # This file
```

## Deploying to Pipecat Cloud

This project is configured for deployment to Pipecat Cloud. You can learn how to deploy to Pipecat Cloud in the [Pipecat Quickstart Guide](https://docs.pipecat.ai/getting-started/quickstart#step-2-deploy-to-production).

Refer to the [Pipecat Cloud Documentation](https://docs.pipecat.ai/deployment/pipecat-cloud/introduction) to learn more about configuring, deploying, and managing your agents in Pipecat Cloud.

## Observability

This project includes observability tools to help you debug and monitor your bot:

### Whisker - Live Pipeline Debugger

**Whisker** is a live graphical debugger that lets you visualize pipelines and debug frames in real time.

With Whisker you can:

- 🗺️ View a live graph of your pipeline
- ⚡ Watch frame processors flash in real time as frames pass through them
- 📌 Select a processor to inspect the frames it has handled
- 🔍 Filter frames by name to quickly find the ones you care about
- 🧵 Select a frame to trace its full path through the pipeline
- 💾 Save and load previous sessions for review and troubleshooting

**To use Whisker:**

1. Run an ngrok tunnel to expose your bot:

   ```bash
   ngrok http 9090
   ```

   > Tip: Use `--subdomain` for a repeatable ngrok URL

2. Navigate to [https://whisker.pipecat.ai/](https://whisker.pipecat.ai/) and enter your ngrok URL (e.g., `your-subdomain.ngrok.io`)

3. Once your bot is running, press connect

### Tail - Terminal Dashboard

**Tail** is a terminal dashboard that lets you monitor your Pipecat sessions in real time.

With Tail you can:

- 📜 Follow system logs in real time
- 💬 Track conversations as they happen
- 🔊 Monitor user and agent audio levels
- 📈 Keep an eye on service metrics and usage

**To use Tail:**

1. Run your bot (in one terminal)

2. Launch Tail in another terminal:
   ```bash
   pipecat tail
   ```
## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)