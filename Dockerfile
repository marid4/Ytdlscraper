FROM kivy/buildozer:latest

USER root
RUN apt-get update && apt-get install -y \
    git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/user/hostcwd
ENTRYPOINT ["buildozer"]
CMD ["android", "debug"]
