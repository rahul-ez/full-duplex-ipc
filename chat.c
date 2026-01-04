#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <mqueue.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <errno.h>

#define MAX_TEXT 1024
#define MAX_NAME 32
#define LOG_FILE "ipc_history.log"

/* --- Global State --- */
mqd_t send_mq, recv_mq, gui_tx_mq, gui_rx_mq;
char self[MAX_NAME], peer[MAX_NAME];
volatile sig_atomic_t keep_running = 1;

/* --- Utilities --- */
void get_timestamp(char *buf, size_t len) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    strftime(buf, len, "%Y-%m-%d %H:%M:%S", t);
}

void log_to_file(const char *tag, const char *message) {
    FILE *f = fopen(LOG_FILE, "a");
    if (f) {
        char ts[32];
        get_timestamp(ts, sizeof(ts));
        fprintf(f, "[%s] [%s] %s\n", ts, tag, message);
        fclose(f);
    }
}

void cleanup() {
    printf("\nShutting down and cleaning up queues...\n");
    mq_close(send_mq);
    mq_close(recv_mq);
    mq_close(gui_tx_mq);
    mq_close(gui_rx_mq);
}

void handle_signal(int sig) {
    keep_running = 0;
    // Force exit if stuck in blocking read
    exit(0); 
}

/* --- Threads --- */

// Logic: Handles Keyboard Input
void *send_thread(void *arg) {
    char input[MAX_TEXT];
    char buffer[MAX_TEXT];
    while (keep_running) {
        printf("%s >> ", self);
        if (!fgets(input, MAX_TEXT, stdin)) continue;
        input[strcspn(input, "\n")] = 0;

        if (strlen(input) == 0) continue;

        snprintf(buffer, MAX_TEXT, "[%s]: %s", self, input);
        
        if (mq_send(send_mq, buffer, strlen(buffer) + 1, 0) == -1) {
            perror("mq_send peer");
        }
        mq_send(gui_tx_mq, buffer, strlen(buffer) + 1, 0);
        log_to_file("CLI_SEND", buffer);
    }
    return NULL;
}

// Logic: Handles Incoming Peer Messages
void *recv_thread(void *arg) {
    char buffer[MAX_TEXT];
    while (keep_running) {
        ssize_t n = mq_receive(recv_mq, buffer, MAX_TEXT, NULL);
        if (n < 0) continue;

        printf("\n%s\n%s >> ", buffer, self);
        fflush(stdout);
        
        mq_send(gui_tx_mq, buffer, strlen(buffer) + 1, 0);
        log_to_file("PEER_RECV", buffer);
    }
    return NULL;
}

// Logic: Handles GUI Input and Echoing
void *gui_relay_thread(void *arg) {
    char buffer[MAX_TEXT];
    while (keep_running) {
        ssize_t n = mq_receive(gui_rx_mq, buffer, MAX_TEXT, NULL);
        if (n < 0) continue;

        char out_buf[MAX_TEXT];
        snprintf(out_buf, MAX_TEXT, "[%s]: %s", self, buffer);
        
        mq_send(send_mq, out_buf, strlen(out_buf) + 1, 0);
        mq_send(gui_tx_mq, out_buf, strlen(out_buf) + 1, 0); 

        printf("\n(GUI) %s\n%s >> ", out_buf, self);
        fflush(stdout);
        log_to_file("GUI_SEND", out_buf);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <self_name> <peer_name>\n", argv[0]);
        return 1;
    }

    atexit(cleanup);
    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    strncpy(self, argv[1], MAX_NAME);
    strncpy(peer, argv[2], MAX_NAME);

    struct mq_attr attr = { .mq_flags = 0, .mq_maxmsg = 10, .mq_msgsize = MAX_TEXT, .mq_curmsgs = 0 };

    // Setup queue names
    char q_send[64], q_recv[64], g_tx[64], g_rx[64];
    snprintf(q_send, 64, "/mq_%s_to_%s", self, peer);
    snprintf(q_recv, 64, "/mq_%s_to_%s", peer, self);
    snprintf(g_tx, 64, "/mq_gui_rx_%s", self);
    snprintf(g_rx, 64, "/mq_gui_tx_%s", self);

    // Open/Create Queues
    send_mq = mq_open(q_send, O_CREAT | O_RDWR, 0666, &attr);
    recv_mq = mq_open(q_recv, O_CREAT | O_RDWR, 0666, &attr);
    gui_tx_mq = mq_open(g_tx, O_CREAT | O_RDWR, 0666, &attr);
    gui_rx_mq = mq_open(g_rx, O_CREAT | O_RDWR, 0666, &attr);

    if (send_mq == -1 || recv_mq == -1 || gui_tx_mq == -1 || gui_rx_mq == -1) {
        perror("mq_open failed");
        return 1;
    }

    printf("--- IPC CHAT SYSTEM STARTED ---\n");
    printf("Identity: %s | Peer: %s\n", self, peer);
    printf("Logging to: %s\n", LOG_FILE);
    printf("-------------------------------\n");

    pthread_t t1, t2, t3;
    pthread_create(&t1, NULL, send_thread, NULL);
    pthread_create(&t2, NULL, recv_thread, NULL);
    pthread_create(&t3, NULL, gui_relay_thread, NULL);

    // Wait for the keyboard thread or signal
    pthread_join(t1, NULL);

    return 0;
}