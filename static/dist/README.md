
# jQuery UI
Tristan added a custom build of jQuery UI to the officer profile page to implement the Payroll accordion 
dropdown widget. A custom version of jQuery UI was needed so that the active state color matches the FDP color scheme. 
Currently this is in use on the officer profile page (officer.html). To prevent unintended side effects the library 
is included only on the officer.html, and the custom build is scoped to elements under the '.jqueryui' class. You can use this library in other places on the site. To do 
this you will need to include the library in the header on that template, and wrap your elements in a div with the 
'jqueryui' class. At the time of writting only the accordion widget is included in the build. You may also need to add 
additional widgets as needed.

Any time the theme needs to be updated, follow the below instructions:

## Update instructions
- Go to https://jqueryui.com/themeroller/
- Configure:
    - Set the Corner Radius to 0px
    - Set the clickable: active state background and border color to #417690
- Change any other settings you need (and update the list above)
- Click Download Theme
- Select the needed widgets (don't select all it will be a giant file!)
  - Accordion
- Add any additional widgets needed (and update the list above)
- Set CSS Scope to .jqueryui
- Click Download
- Unzip and rename the folder to jquery-ui-custom and replace the one in this directory (/static/dist/)
- Commit with a message that reads "Update jquery-ui library"
