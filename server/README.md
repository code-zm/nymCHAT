## Discovery Node
A discovery / message relay service used by nymCHAT clients. 

## Installation

**Prerequisities**
1. Git - to clone the repo
2. Docker - to run in everything in container 

#### Step 1: Clone the Repo
Download the project to your local machine:
```sh
git clone https://github.com/code-zm/nymCHAT.git
cd nymCHAT/server
```

#### Step 2: Configuration
Before we build the Docker image, we have to do some setup.
First, create the `.env` file:
```sh
cp .env.example .env
```

*Note: no changes are necessary, simply copying is fine. If you want your nym-client itself to have a custom name, set NYM_CLIENT_ID*

Next, setup your encryption password. This will be used to unlock your keys. 
```sh
echo "your-secure-password" > password.txt
```

#### Step 3. Build the Docker Image
This installs dependencies and sets up the nym-client.
```sh
docker build -t nymserver:latest .
```

#### Step 4: Run the Docker Container
Since we are running a discovery service, we want persistent storage across runs. The following command achieves this:
```sh
docker run -d \
    -v $(pwd)/nym-data:/root/.nym:rw \
    -v $(pwd)/storage:/app/storage \
    --name nymchat-server \
    nymserver:latest
```

**Command Arguments**
- `d` -> Runs the container in the background
- `--name nymdir` -> Container name
- `-v $(pwd)/nym-data:/root/.nym:rw` -> Nym-Client identity persistance
- `-v $(pwd)/storage:/app/storage` -> Logs and DB persistance

#### Step 5: Manage the Container
Here are some common docker commands you may find useful:
*Note: To allow docker to run without sudo, add your user to the docker group. `sudo usermod -aG docker $USER`*
**Check Running Containers**
```sh
docker ps
```

**View Logs**
```sh
docker logs -f nymchat-server
```

**Stop the Container**
```sh
docker stop nymchat-server
```

**Start the Container**
```sh
docker start nymchat-server
```

**Remove the Container**
```sh
docker rm -f nymchat-server
```