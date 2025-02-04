
## Backend of wayfind app




## How to run the project



- run development server `fastapi dev main.py`


## to generate a salt use this
`bash
openssl rand -hex 32
`




## Features

- [] Scan contact.
- [] Create Group
- [] Add People in group
- [] Each member must have application installed, notification and Location sharing On.
- [] People must Login using mobile number and with OTP verification.
- [] Admin can add co admins
- [] Admin can decide the route,
- [] A route will get rendered
- [] Admin Can assign Lead. 
- [] In that path each peoples location will, get updated as they move
- [] Location update would happen per minute.
- [] There would be call feature, infront of each users name a small call button, that they can use to call with one click.
- [] SOS button, when clicked it will admins notification that something went wrong.
- [] Admin can click on the users Icon and it would open google map and u can reach to their location.
- [] For admins there would be button to gather around. when clicked it would send all group members notification and vibration, so all people can come at one place that was decided previously.
- [] User can leave the group or Admin can dissolve the group when ride is complete.
- [] There would be press to speak feature, when said something, it will do a broadcast and people can hear what was said.



## tasks 

- [X] login page
- [X] Signup
- [X] Update User Profile,
- [] Create Group
- [] Share Link of Group
- [] People Can Join Via Group Link. 
- [] Group Settings, Max can have 10 People in a Group
- [] Render Map
- [] One user can be in max one group at a time. Upgrade to be in multiple group
- [] Render User marker using User location
- [] WebSocket connection to each group.
- [] share user location every minute on in backend
- [] Broadcast the location in that group.
- [] Speak Feature, take the 30 second audio, and broadcast in the Group
- [] Buy me coffee link
- [] Membership Plan, to add more people in the Group, and create more group.

- [] Do stress testing, for 1000s of user location flowing in the system, in 100s of groups.
- [] Add free version of sentry.



## Deployment
- [] Deployment using Gitlab CICD Directly to AWS
- [] App deployment to playstore and app store