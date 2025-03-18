## nymDirectory
A discovery / remailer service used by nymCHAT clients. 

## Installation
**Prerequisities**
1. Git - to clone the repo
2. Docker - to run in everything in container
3. Rust- only needed if not on linux, you will have to build the nym-client from source. 

#### Step 1: Clone the Repo
Download the project to your local machine:
```sh
git clone https://github.com/code-zm/nymCHAT.git
cd nymCHAT/nymDirectory
```

#### Step 2: Configuration
Before we build the Docker image, we have setup some config files.
First, Create the `.env` file:
```sh
cp .env.example .env
```

*Note: if you use a custom `NYM_CLIENT_ID`, make sure you set all env vars to match it.*

Next, setup your encryption password. This will be used to "unlock" your keys. 
```sh
echo "your-secure-password" > password.txt
chmod 600 password.txt
```

#### Step 3. Build the Docker Image
This installs dependencies and sets up the nym-client.
```sh
docker build -t nymdir:latest .
```

#### Step 4: Run the Docker Container
Since we are running a discovery service, we want persistent storage across runs. The following command achieves this:
```sh
docker run -d \
    -v $(pwd)/nym-data:/root/.nym:rw \
    -v $(pwd)/storage:/app/storage \
    --name nym-dir \
    nymdir:latest
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
docker logs -f nym-dir
```

**Stop the Container**
```sh
docker stop nym-dir
```

**Start the Container**
```sh
docker start nym-dir
```

**Remove the Container**
```sh
docker rm -f nym-dir
```