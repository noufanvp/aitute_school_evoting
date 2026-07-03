from bs4 import BeautifulSoup

with open('/home/noufan/Desktop/Learning/ROTECH/projects/E_Voting_V2/voting/templates/voting/results.html', 'r') as f:
    content = f.read()

import re
clean_content = re.sub(r'{%.*?%}', '', content)
clean_content = re.sub(r'{{.*?}}', '', clean_content)

soup = BeautifulSoup(clean_content, 'html.parser')
body = soup.find('body')
for child in body.children:
    if child.name:
        print(f"Child: {child.name}, class: {child.get('class', '')}")
