# SFMC Image Migration in Email

This code helps in migrating images from externally hosted URL to SFMC in your email 

#### This code performs

1. Reads html file that contains email 
2. Finds all images in image tag
3. Uploads it to SFMC using asset api 
4. Replace the old image url with new SFMC image url and create a new html file with suffix '-image-migrated'