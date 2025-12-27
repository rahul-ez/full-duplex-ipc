#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <mqueue.h>
#include <fcntl.h>
#include <unistd.h>

#define MQ_A_TO_B "/mq_a_to_b"
#define MQ_B_TO_A "/mq_b_to_a"

#define MAX_TEXT 256

typedef struct {
    char text[MAX_TEXT];
} message_t;

/* Global message queues */
mqd_t send_mq, recv_mq;

/* Process role: 'A' or 'B' */
char ROLE;

/* ================= EVENT LOGGING ================= */
void log_event(const char* event) {
    FILE* fp = fopen("ipc_log.txt", "a");
    if (fp) {
        fprintf(fp, "%s\n", event);
        fclose(fp);
    }
}

/* ================= SEND THREAD ================= */
void* send_thread_func(void* arg) {
    message_t msg;
    char logbuf[300];

    while (1) {
        if (fgets(msg.text, MAX_TEXT, stdin) == NULL)
            break;

        mq_send(send_mq, (char*)&msg, sizeof(msg), 0);

        snprintf(logbuf, sizeof(logbuf),
                 "[SEND] %c->%c : %s",
                 ROLE,
                 (ROLE == 'A') ? 'B' : 'A',
                 msg.text);
        log_event(logbuf);

        if (strncmp(msg.text, "exit", 4) == 0)
            break;
    }
    return NULL;
}

/* ================= RECEIVE THREAD ================= */
void* recv_thread_func(void* arg) {
    message_t msg;
    char logbuf[300];

    while (1) {
        mq_receive(recv_mq, (char*)&msg, sizeof(msg), NULL);

        snprintf(logbuf, sizeof(logbuf),
                 "[RECV] %c<-%c : %s",
                 ROLE,
                 (ROLE == 'A') ? 'B' : 'A',
                 msg.text);
        log_event(logbuf);

        if (strncmp(msg.text, "exit", 4) == 0) {
            printf("\nPeer exited the chat.\n");
            break;
        }

        printf("\nPeer: %s", msg.text);
        fflush(stdout);
    }
    return NULL;
}

/* ================= MAIN ================= */
int main(int argc, char* argv[]) {
    if (argc != 2) {
        printf("Usage: %s <A|B>\n", argv[0]);
        exit(1);
    }

    ROLE = argv[1][0];

    struct mq_attr attr;
    attr.mq_flags = 0;
    attr.mq_maxmsg = 10;
    attr.mq_msgsize = sizeof(message_t);
    attr.mq_curmsgs = 0;

    /* ---------- PROCESS A ---------- */
    if (ROLE == 'A') {
        send_mq = mq_open(MQ_A_TO_B, O_CREAT | O_WRONLY, 0644, &attr);
        recv_mq = mq_open(MQ_B_TO_A, O_CREAT | O_RDONLY, 0644, &attr);
        printf("Process A started\n");
    }
    /* ---------- PROCESS B ---------- */
    else if (ROLE == 'B') {
        send_mq = mq_open(MQ_B_TO_A, O_WRONLY);
        recv_mq = mq_open(MQ_A_TO_B, O_RDONLY);
        printf("Process B started\n");
    }
    else {
        printf("Invalid argument. Use A or B.\n");
        exit(1);
    }

    pthread_t send_thread, recv_thread;
    pthread_create(&send_thread, NULL, send_thread_func, NULL);
    pthread_create(&recv_thread, NULL, recv_thread_func, NULL);

    pthread_join(send_thread, NULL);
    pthread_cancel(recv_thread);

    mq_close(send_mq);
    mq_close(recv_mq);

    if (ROLE == 'A') {
        mq_unlink(MQ_A_TO_B);
        mq_unlink(MQ_B_TO_A);
    }

    printf("Chat terminated.\n");
    return 0;
}
