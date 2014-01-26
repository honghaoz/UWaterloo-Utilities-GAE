#lang racket
; CS136 W14: Assignment 1bonus
; Honghao Zhang 20530902

(require "uw-api.rkt")

; UWaterloo Course Notifier (Scheme Version)
; uw-course-notifier-menu is an scheme version app
; This is the only entry to this app
; Purpose:
;   At the begining of a term, students always cannot enroll into his dream class.
;   So, this app is for students of UWaterloo, mainly used for setting an email alert for 
;   a class.
;   If an opening is found, we will send an email notification to you.
;   connect to my web application, http://uw.honghaoz.com/uw-cen.
(provide uw-course-notifier-menu)

(require net/url)
(require json)

; ***************************************** ;
; get current term, for now, it will return 1141
; ***************************************** ;
; 
(define (get-current-term)
  (define (hash->strlist h)
    (cond [(list? h) (map hash->strlist h)]
          [(symbol? h) (symbol->string h)]
          [(not (hash? h)) h]
          [else (hash-map h (lambda (k v) (list (hash->strlist k) (hash->strlist v))))]))
  (define uw-cen-base "http://uw.honghaoz.com/uw-cen")
  (define api-lang "json")
  (define url (string->url (string-append uw-cen-base "." api-lang)))
  (define json (read-json (get-pure-port url)))
 
  (define (get-info each req-info)
    (second (first (filter (lambda (x) (string=? (first x) req-info)) each))))  
  (string->number (get-info (hash->strlist json) "current_term")))

; ***************************************** ;
; Set email alert
; ***************************************** ;
;
(define (set-alert term subject catalog course-num email)
  (define (hash->strlist h)
    (cond [(list? h) (map hash->strlist h)]
          [(symbol? h) (symbol->string h)]
          [(not (hash? h)) h]
          [else (hash-map h (lambda (k v) (list (hash->strlist k) (hash->strlist v))))]))
  (define uw-cen-base "http://uw.honghaoz.com/uw-cen")
  (define api-lang "json")
  (define url (string->url (string-append uw-cen-base "/" 
                                          (number->string term) "-" 
                                          subject "-" 
                                          (number->string catalog) "-"
                                          (number->string course-num) "-"
                                          email
                                          "." api-lang)))
  (define json (read-json (get-pure-port url)))
  (define (get-info each req-info)
    (second (first (filter (lambda (x) (string=? (first x) req-info)) each))))  
  (get-info (hash->strlist json) "response"))

; ***************************************** ;
; used for choose a catalog num 
; ***************************************** ;
(define (get-courses subject)
  (define result (uw-api (string-append "/courses/" subject)))
  (define (get-info each req-info)
    (second (first (filter (lambda (x) (string=? (first x) req-info)) each))))
    
  (define i 0)
  
  (cond
    [(false? result) (list)]
    [else (map (lambda (each) (set! i (add1 i)) (string-append (number->string i)
                                                               ": "
                                                               (get-info each "subject")
                                                               " "
                                                               (get-info each "catalog_number")
                                                               " "
                                                               (get-info each "title"))) result)]))

(define (choose-course course-list)
  ;print courses
  (for* ([the-course course-list])
    (printf the-course)
    (printf "\n"))
  ;choose
  (printf "Input the # of the course you want to choose: ")
  (define choosed-num 0)
  (define input-switch false)
  (do ()
    (input-switch)
    (set! choosed-num (read))
    (if (and (number? choosed-num) (< 0 choosed-num) (<= choosed-num (length course-list))) (set! input-switch true) 
        (printf "Not a proper #, please input again: ")))
  (define chooses-str (list-ref course-list (- choosed-num 1)))
  ;extract the catalog num
  (define i 0)
  (define ith-white 0)
  (define start 0)
  (define end 0)
  (for* ([each-char (string->list chooses-str)])
    (cond
      [(and (= ith-white 1) (char-whitespace? each-char)) (set! start (add1 i))
                                                          (set! ith-white (add1 ith-white))
                                                          (set! i (add1 i))]
      [(and (= ith-white 2) (char-whitespace? each-char)) (set! end i)
                                                          (set! ith-white (add1 ith-white))
                                                          (set! i (add1 i))]
      [else (cond
              [(char-whitespace? each-char) (set! ith-white (add1 ith-white))
                                            (set! i (add1 i))]
              [else (set! i (add1 i))])]))
  (substring chooses-str start end))


(define (section-info term subject catalog section)
  (define result (uw-api (string-append "/terms/" (number->string term) "/" subject "/" (number->string catalog) "/schedule")))
  ; get-info: (listof X) String -> Any
  ;   PRE: true
  ;   POST: produces the information matches req-info
  ; Purpose: consumes the list of courses and req-info, produces the information matches req-info
  (define (get-info each req-info)
    (second (first (filter (lambda (x) (string=? (first x) req-info)) each))))
  (cond
    [(false? result) "null"]
    [else (define the-sec (first (filter (lambda (each-course) (string=? section (get-info each-course "section"))) result)))
          (define the-sec-info (first (get-info the-sec "classes")))
          the-sec-info
          (cond
            [(empty? the-sec) "null"]
            [else (define date (get-info the-sec-info "date"))
                  (define location (get-info the-sec-info "location"))
                  (define instructors (get-info the-sec-info "instructors"))
                  (define time (string-append (get-info date "start_time")
                                              "-"
                                              (get-info date "end_time")
                                              " "
                                              (get-info date "weekdays")))
                  (define building (string-append (get-info location "building")
                                                  " "
                                                  (get-info location "room")))
                  (define the-instructor (first instructors))
                  (list time building the-instructor)])
          ]))


(define (get-lecs term subject catalog)
  ; get the result
  (define result (uw-api (string-append "/terms/" (number->string term) "/" subject "/" (number->string catalog) "/schedule")))
  ; get-info: (listof X) String -> Any
  ;   PRE: true
  ;   POST: produces the information matches req-info
  ; Purpose: consumes the list of courses and req-info, produces the information matches req-info
  (define (get-info each req-info)
    (second (first (filter (lambda (x) (string=? (first x) req-info)) each))))  
  (cond
    [(false? result) (list)]
    [else (define result-lec (filter (lambda (each-course) (string=? "LEC" (substring (get-info each-course "section") 0 3))) result))
          (map (lambda (each-course) (define each-sec (get-info each-course "section")) 
                 (list (get-info each-course "section")
                       (get-info each-course "enrollment_capacity")
                       (get-info each-course "enrollment_total")
                       (section-info term subject catalog each-sec)
                       (get-info each-course "class_number")))
               result-lec)]))

(define (print-lecs lec-list)
  (printf "#  Section#\tEnroll\tCapacity \tTime       \tBuilding \tInstructor\n")
  (define i 0)
  (for* ([the-lec lec-list])
    (set! i (add1 i))
    (printf "~a  ~a \t~a \t~a \t~a \t~a \t~a\n" 
            i
            (first the-lec)  
            (third the-lec)
            (second the-lec)
            (first (fourth the-lec))
            (second (fourth the-lec))
            (third (fourth the-lec)))))

; ***************************************** ;
; global variables
; ***************************************** ;

(define term (get-current-term))
(define subject "")
(define catalog_num "")

; ***************************************** ;
; menu (main fuction)
; ***************************************** ;
(define (uw-course-notifier-menu)
  (printf "Welcome to UWaterloo Course Notifier (Scheme Version)\n")
  (printf "Please input the subject you are looking for: ")
  (set! subject (symbol->string (read)))
  (printf "Please input the course number (option, input 'no' to skip): ")
  (define input-switch false)
  (do ()
    (input-switch)
    (set! catalog_num (read))
    (if (or (number? catalog_num) (symbol=? catalog_num 'no)) (set! input-switch true)
        (printf "Not a proper input, please input again: ")))
  (if (and (not (number? catalog_num)) (symbol=? catalog_num 'no)) (set! catalog_num (choose-course (get-courses subject))) 
      (set! catalog_num (number->string catalog_num)))
  
  (define lec-list (get-lecs term subject (string->number catalog_num)))
  (printf (string-append subject " " catalog_num " :\n"))
  (print-lecs lec-list)
  (printf "Input the # of the section you want to notify: ")
  
  (define choosed-sec 0)
  (define input-switch1 false)
  (do ()
    (input-switch1)
    (set! choosed-sec (read))
    (if (and (number? choosed-sec) (< 0 choosed-sec) (<= choosed-sec (length lec-list))) (set! input-switch1 true) 
        (printf "Not a proper #, please input again: ")))
  (define choosed-lec (list-ref lec-list (- choosed-sec 1)))
  (printf "You choosed ~a ~a ~a\n" subject catalog_num (first choosed-lec))
  (printf "Input your eamil address to receive notification: ")
  (define email (symbol->string (read)))
  (define response (set-alert term subject (string->number catalog_num) (fifth choosed-lec) email))
  (printf "Set ~a ~a ~a notification to ~a ~a\nYou will receive a confirm email! Thanks for using UWaterloo Course Notifier!" 
          subject
          catalog_num
          (first choosed-lec)
          email
          response))
;(uw-course-notifier-menu)