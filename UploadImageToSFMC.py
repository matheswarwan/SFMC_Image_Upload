from bs4 import BeautifulSoup
import requests
import base64

SAPDomains = ['mail.example.com'] # Enter your SAP domain or other domains from where image migration is not required
tse = '<ENTER>' # Just the TSE value; do not include rest.marketingcloudapis.com or auth.marketingcloudapis.com
clientId = '<ENTER>'
clientSecret = '<ENTER>'
mid = 515010937

file_name_to_process = '<Your_html_file_name_to_process>' # Enter your email file name that contains valid html and image urls hosted in external / non-SFMC system

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Function to read HTML content from a file
def read_html_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Modified function to fetch and encode image content from a URL
def encode_url_to_base64(image_url):
    response = requests.get(image_url)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode('utf-8')
    else:
        raise Exception(f"Failed to fetch image: HTTP {response.status_code}")


def get_user_decision(suggested_name, existing_asset_url):
    print(bcolors.OKBLUE + f"The name '{suggested_name}' is already taken and available in SFMC in url {existing_asset_url}. Do you want to use the existing asset? (yes/no)" + bcolors.ENDC)
    decision = input().lower()
    if decision == 'yes' or decision == 'y':
        return True, None  # Continue with existing asset
    else:
        print("Enter a new name for the asset:")
        existing_asset_url_type = existing_asset_url.split('.')[-1]
        print('existing_asset_url_type : ' , existing_asset_url_type)
        while True:
            new_name = input("Enter the new name (must be more than 5 characters and contain no dots): ")
            if '.' not in new_name and len(new_name) >= 5:
                new_name = new_name + '.' + existing_asset_url_type
                print('new_name:', new_name)
                return False, new_name  # Exit loop with valid new name
            else:
                print("Invalid input. Please ensure the name is more than 5 characters and contains no dots.")

def search_asset_by_name(access_token, asset_name):
    # print('[access_token]: ', access_token)
    # print('[asset_name]: ', asset_name)
    search_url = f'https://{tse}.rest.marketingcloudapis.com/asset/v1/content/assets?$filter=name eq ' + asset_name
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(search_url, headers=headers)
    # print('[search_asset_by_name]: ' , response.json())
    if response.status_code == 200 and response.json()['count'] > 0:
        return response.json()['items'][0]['fileProperties']['publishedURL']
    return None

# Updated function to include fileName and handle the SFMC API requirements
def upload_image_to_sfmc(image_url,file_name):
    auth_response = requests.post(
        f'https://{tse}.auth.marketingcloudapis.com/v2/token',
        json={
            'client_id': clientId,
            'client_secret': clientSecret,
            'grant_type': 'client_credentials',
            'account_id': mid
        }
    )
    access_token = auth_response.json().get('access_token')

    # print('[access_token]: ', access_token)
    # print('[Old_image_url]: ', image_url)

    base64_encoded_content = encode_url_to_base64(image_url)

    # print('[base64_encoded_content]: ', '**YES**')

    # Extract the file name from the URL to use in the asset data
    file_type = file_name.split('.')[-1]

    # Updated asset_data with fileName
    asset_data = {
        'name': file_name,  # More meaningful name based on the file name
        'assetType': {'name': file_type, 'id': 23},  # Example, adjust as needed
        'file': base64_encoded_content,  # Encoded content
        'FileProperties': { 'fileName': file_name  } 
    }

    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.post(
        f'https://{tse}.rest.marketingcloudapis.com/asset/v1/content/assets',
        json=asset_data,
        headers=headers
    )

    # print('[SFMC Image upload response code]: ' , response.json())

    if response.status_code == 200 or response.status_code == 201:
        print(bcolors.OKGREEN +'[SFMC Image upload status - Success; Response code]: ' , response.status_code  + bcolors.ENDC)
        new_url = response.json().get('fileProperties', {}).get('publishedURL')
        # print('[asset_data]: ', asset_data)
        # print('[response]: ', response.json())
        print('[new_url]: ', new_url)
        return new_url
    elif response.status_code != 201:
        error_response = response.json()
        if error_response.get('errorcode') == 10006:  # Validation error for unique name
            print(bcolors.FAIL +'[SFMC Image upload status - Error: Duplicate Name; Response code]: ' , response.status_code ,  bcolors.ENDC)
            for error in error_response.get('validationErrors', []):
                if error.get('errorcode') == 118039:  # Non-unique name error
                    existing_asset_url = search_asset_by_name(access_token, file_name)
                    continue_with_existing, new_name = get_user_decision(file_name, existing_asset_url)
                    if continue_with_existing:
                        print(f"Using existing asset URL: {existing_asset_url}")
                        return existing_asset_url
                    else:
                        return upload_image_to_sfmc(image_url, new_name)  # Recursive call with new name
                if error.get('errorcode') == 118112: # File name must be at least five characters error 
                    print(bcolors.FAIL +'[SFMC Image upload status - Error: Name is not 5 char long; Response code]: ' , response.status_code , bcolors.ENDC)

                    new_name = 'SFMC_' + file_name # Prepend SFMC_ to the image name to make it 5+ characters
                    print('[Reupload with new name]: ', new_name)
                    return upload_image_to_sfmc(image_url, new_name) 
    else:
        print('[response]: ', response.json())
        raise Exception("Failed to upload image to SFMC")

# Function to replace old image URLs with new ones
def replace_image_urls(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    images = soup.find_all('img')
    for img in images:
        old_url = img['src']
        if not any(domain in old_url for domain in SAPDomains):
            print('Uploading image ' , old_url)
            file_name = old_url.split('/')[-1]
            new_url = upload_image_to_sfmc(old_url, file_name)
            img['src'] = new_url
    return str(soup)


# Main workflow
def migrate_images_in_html(file_path):
    html_content = read_html_file(file_path)
    updated_html_content = replace_image_urls(html_content)
    new_file_path = f"{file_path.split('.html')[0]}-image-migrated.html"
    with open(new_file_path, 'w', encoding='utf-8') as file:
        file.write(updated_html_content)
    print(bcolors.HEADER + f"Migration completed. New file saved at: {new_file_path}" + bcolors.ENDC)

migrate_images_in_html(file_name_to_process)
