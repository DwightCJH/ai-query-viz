# CSV-ision 🧿 (Local Development Setup)

Note: requires older than Python 3.12

Also, admittedly it's quite buggy

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-directory>
    ```

    **Configure Backend Environment Variables:**
    *   Create a file named `.env` and add your API key.


    **Set up Dependencies:**
    *   Create and activate a virtual environment 
        ```bash
        # Linux/macOS
        python3 -m venv venv
        source venv/bin/activate

        # Windows (cmd)
        python -m venv venv
        venv\Scripts\activate.bat

        # Windows (PowerShell)
        python -m venv venv
        venv\Scripts\Activate.ps1
        ```

        Install requirements
        ```bash
        pip install -r requirements.txt
        ```

## Running the Application

You will need **two separate terminal windows** open.

1.  **Terminal 1: Run the Backend**
    *   Navigate to the `backend` directory.
        ```bash
        cd backend
        ```
    *   Start the Flask development server:
        ```bash
        python app.py
        ```
    *   You should see output indicating the server is running, typically on `http://127.0.0.1:5000` or `http://0.0.0.0:5000`. Leave this terminal running.

2.  **Terminal 2: Run the Frontend**
    *   Navigate to the `frontend` directory.
        ```bash
        cd frontend
        ```
    *   Start the Streamlit application:
        ```bash
        streamlit run app.py
        ```

## Accessing the Application

*   Open your web browser and navigate to the URL provided by Streamlit (usually `http://localhost:8501`).
*   The frontend will communicate with the backend running on `localhost:5000` (as configured by the default `BACKEND_URL` in `frontend/app.py` when the environment variable isn't set).

---

Remember to deactivate the virtual environments when you are finished:

```bash
deactivate
