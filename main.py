from dotenv import load_dotenv
import os
from PIL import Image
import io
from instagrapi import Client
import time
import logging
import httpx
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pickle

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_credentials():
    """Load Hugging Face and Instagram credentials from .env file."""
    try:
        load_dotenv()
        hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        ig_username = os.getenv("INSTAGRAM_USERNAME")
        ig_password = os.getenv("INSTAGRAM_PASSWORD")

        if not all([hf_token, ig_username, ig_password]):
            raise ValueError("Missing credentials in .env file")
        logger.info("Credentials loaded successfully")

        return {"hf_token": hf_token, "ig_username": ig_username, "ig_password": ig_password}
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        raise

def generate_image(prompt, hf_token):
    """Generate image from Hugging Face API using StabilityAI Stable Diffusion 3.5 Large or any other model."""
    try:
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json",
            "Accept": "image/png"
        }

        payload = {
            "inputs": prompt
        }

        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large"

        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)

        if response.status_code != 200:
            logging.error(f"HF API Error {response.status_code}: {response.text}")
            raise Exception(f"Image generation failed: {response.status_code}")

        logging.info("Image generated successfully from HF API")
        return response.content  # PNG image in bytes

    except Exception as e:
        logging.error(f"Error generating image: {repr(e)}")
        logging.warning("Generating placeholder image instead")
        placeholder = Image.new("RGB", (512, 512), color="gray")
        buffer = io.BytesIO()
        placeholder.save(buffer, format="PNG")
        return buffer.getvalue()


def save_image(image_data, output_dir="images", filename_prefix="post"):
    """Save image as JPG with Instagram-compatible size."""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.jpg")

        image = Image.open(io.BytesIO(image_data))
        image = image.resize((1080, 1080), Image.LANCZOS)
        image = image.convert("RGB")
        image.save(file_path, "JPEG", quality=95)
        logger.info(f"Image saved to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving image: {e}")
        raise

def init_instagram_client(username, password, session_file="ig_session.json"):
  """Initialize and authenticate Instagram client with session persistence."""
  try:
      cl = Client()
      cl.delay_range = [1, 5]  # Random delays to avoid detection

      if os.path.exists(session_file):
          cl.load_settings(session_file)
          try:
              cl.get_timeline_feed()  # Try a harmless call to validate session
              logger.info("Loaded existing Instagram session.")
              return cl
          except Exception:
              logger.warning("Session expired or invalid. Logging in again.")

      # Fallback to fresh login
      cl.login(username, password)
      cl.dump_settings(session_file)
      logger.info("Logged in and saved new Instagram session.")
      return cl

  except Exception as e:
      logger.error(f"Error initializing Instagram client: {e}")
      raise

def load_cookies(driver, cookies_file):
    if os.path.exists(cookies_file):
        with open(cookies_file, "rb") as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
        print("✅ Cookies loaded.")
    else:
        raise Exception("❌ Cookies file not found. Run login script first.")

def post_to_instagram_facebook(cl, image_path, caption):
    """Post image to Facebook and Instagram with caption."""
    try:
        # Convert to absolute path for both Facebook and Instagram
        full_image_path = os.path.abspath(image_path)
        logger.info(f"Using image path: {full_image_path}")

        # Launch Chrome with options
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        driver = webdriver.Chrome(options=options)

        # Load Facebook and inject cookies
        driver.get("https://www.facebook.com/")
        driver.delete_all_cookies()
        load_cookies(driver, "fb_cookies.pkl")
        driver.get("https://www.facebook.com/me")
        time.sleep(5)

        # Escape any modals
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(2)

        # Click "What's on your mind" post box
        post_box = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and contains(., \"on your mind\")]"))
        )
        post_box.click()
        time.sleep(3)

        # Facebook creates file input dynamically — wait and find it
        upload_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file' and @accept='image/*,image/heif,image/heic,video/*,video/mp4,video/x-m4v,video/x-matroska,.mkv']"))
        )
        upload_input.send_keys(full_image_path)
        logger.info("📎 Image path sent to file input.")
        time.sleep(10)  # Give time for image to render

        # Wait for the second popup (after image render)
        caption_box = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']//div[@role='textbox']"))
        )
        caption_box.click()
        caption_box.send_keys(caption)
        logger.info("✅ Caption added in the second popup.")
        time.sleep(2)

        # Now locate the post button *within* the active dialog
        post_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='dialog']//div[@aria-label='Post']"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", post_button)
        time.sleep(1)

        try:
            post_button.click()
        except Exception:
            logger.warning("⚠️ Click intercepted, forcing click via JavaScript.")
            driver.execute_script("arguments[0].click();", post_button)

        logger.info("✅ Facebook post published.")

        try:
            post_button.click()
        except Exception:
            logger.warning("⚠️ Click intercepted, forcing click via JavaScript.")
            driver.execute_script("arguments[0].click();", post_button)

        logger.info("✅ Facebook post published.")
        time.sleep(10)
        driver.quit()

        media = cl.photo_upload(
            path=image_path,
            caption=caption
        )
        logger.info(f"Posted to Instagram, Media ID: {media.pk}")

        return media.pk

    except Exception as e:
        logger.error(f"Error posting to Instagram: {e}")
        raise

def main():
    """Main function to generate and post promotional image."""
    try:
        # Define prompt and caption
        prompt = "A sleek, modern web development workspace with a laptop displaying a vibrant website, surrounded by clean code snippets, glowing UI elements, and a futuristic digital background, professional and tech-inspired, high detail, 512x512 resolution"
        caption = "Elevate your online presence with our expert web development services! From stunning websites to powerful e-commerce platforms, we build your digital dreams. Contact us today! #WebDevelopment #WebDesign #TechSolutions" + " "

        # Load credentials
        creds = load_credentials()
        hf_token = creds["hf_token"]

        # Generate and save image
        # image_data = generate_image(prompt, hf_token)
        # image_path = save_image(image_data)
        image_path = "images/post_20250715_104607.jpg"

        # Initialize Instagram client and post
        ig_client = init_instagram_client(creds["ig_username"], creds["ig_password"])
        media_id = post_to_instagram_facebook(ig_client, image_path, caption)

        logger.info(f"Success! Posted promotional image with Media ID: {media_id}")
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise

if __name__ == "__main__":
    main()