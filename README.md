# LLM Analysis Quiz

This is a FastAPI application for the LLM Analysis Quiz project, designed to solve data-related quizzes automatically.

## Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/llm-quiz-app.git
   cd llm-quiz-app
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

4. Create a `.env` file with your configuration:
   ```
   EMAIL=your-email@example.com
   SECRET=your-secret-key
   MAX_QUIZ_SECONDS=180
   ```

5. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Deployment to Vercel

1. Push your code to a GitHub repository.

2. Go to [Vercel](https://vercel.com) and import your repository.

3. Configure the project:
   - Set the framework to "Python"
   - Set the build command to:
     ```
     chmod +x vercel_build.sh && ./vercel_build.sh
     ```
   - Set the output directory to `public`
   - Add these environment variables:
     - `PYTHON_VERSION`: `3.9.16`
     - `PLAYWRIGHT_BROWSERS_PATH`: `0`
     - `EMAIL`: Your email
     - `SECRET`: Your secret key
     - `MAX_QUIZ_SECONDS`: `180`

4. Click "Deploy"

## Project Structure

- `app/`: Main application code
  - `main.py`: FastAPI application
  - `solver.py`: Quiz solving logic
  - `config.py`: Configuration management
  - `submitter.py`: Answer submission logic
  - `utils.py`: Utility functions
- `api/`: Vercel serverless function
  - `index.py`: Vercel handler
- `vercel.json`: Vercel configuration
- `requirements.txt`: Python dependencies
- `runtime.txt`: Python version
- `vercel_build.sh`: Build script

## Testing

You can test the API using curl:

```bash
curl -X POST https://your-vercel-app.vercel.app/api/task \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret-key",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

## License

MIT