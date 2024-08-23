/**
 * StrapBot configuration file for PM2.
 * 
 * Rename this file to ecosystem.config.js and change the settings accordingly before use.
 */

module.exports = {
    apps: [
        {
            name: "strapbot",
            script: "strapbot.py",
            interpreter: "/usr/bin/python3", // adjust this to your python3 path

            // 1 year, so it only stops when the bot is ready to be stopped
            kill_timeout: 31536000,
            post_update: ["pip install -Ur requirements.txt"],
            env: {},
            env_production: {}
        },
        {
            name: "sb-server",
            script: "server.py",
            interpreter: "/usr/bin/python3", // adjust this to your python3 path
            kill_timeout: 600000, // 10 minutes
            post_update: ["pip install -Ur requirements.server.txt"],
            env: {
                SERVER_DEBUG: "true",
                SERVER_DEV: "true",
            },
            env_production: {
                SERVER_DEBUG: "false",
                SERVER_DEV: "false",
            },
        }
    ]
};
