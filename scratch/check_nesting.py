from bs4 import BeautifulSoup

with open('/home/noufan/Desktop/Learning/ROTECH/projects/E_Voting_V2/voting/templates/voting/results.html', 'r') as f:
    content = f.read()

# Replace django tags with placeholders to prevent BS4 parsing issues
import re
clean_content = re.sub(r'{%.*?%}', '', content)
clean_content = re.sub(r'{{.*?}}', '', clean_content)

soup = BeautifulSoup(clean_content, 'html.parser')
# Find the footer
footer = soup.find('div', class_='footer')
if footer:
    # Print the parent tags of the footer
    parent = footer.parent
    parents = []
    while parent:
        parents.append(f"{parent.name}.{parent.get('class', '')}")
        parent = parent.parent
    print("Footer parents:", " -> ".join(parents))
else:
    print("Footer not found")
