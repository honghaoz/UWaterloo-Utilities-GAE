#lang racket

; A simple interface for the uWaterloo API
; See: https://github.com/uWaterloo/api-documentation
; for more information

; Developed by Dave Tompkins [dtompkins AT uwaterloo.ca]
; for cs136 assignments

; version 1.0 [January 2014]

(provide uw-api)

; an APIResult is one of:
; * (list "key" value) [where value is (union Num String)]
; * (list "key" APIResult)               
; * (listof APIResult)

; uw-api: String -> (union APIResult #f)
;   PRE:  you can connect to UW (have online access)
;   POST: produces an APIResult (see above) or
;         #f if s is an invalid query or an empty result

; (uw-api s) will make in inquiry to the UWaterloo API.
;   The format of the results will depend on the API selected,
;   but will typically be a list of lists, where each sublist
;   is a key/value pair.


; EXAMPLES:

; (uw-api "/weather/current")
; (uw-api "/events/holidays")
; (uw-api "/courses/CS/136")
; (uw-api "/terms/1141/CS/136/schedule")
; (uw-api "/foodservices/products/2189")
; (uw-api "/foodservices/2014/3/menu")
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(require net/url)
(require json)

; (see documentation above)
(define (uw-api s)
  ; produce value for key k in hash h,
  ;   or produce f if h is invalid or k does not exist in h
  (define (safe-hash-ref h k f)
    (if (and (hash? h) (hash-has-key? h k)) (hash-ref h k) f))
  ; recursively convert hash h to a list of lists,
  ;   where each sublist is (list "key" value)
  (define (hash->strlist h)
    (cond [(list? h) (map hash->strlist h)]
          [(symbol? h) (symbol->string h)]
          [(not (hash? h)) h]
          [else (hash-map h (lambda (k v) (list (hash->strlist k) (hash->strlist v))))]))
  (define api-base "https://api.uwaterloo.ca/v2")
  (define api-lang "json")  
  (define api-key "abc498ac42354084bf594d52f5570977")
  (define url (string->url (string-append api-base s "." api-lang "?key=" api-key)))
  (define json (read-json (get-pure-port url)))
  (define result (hash->strlist (safe-hash-ref json 'data (make-hash))))
  (if (empty? result) #f result))
