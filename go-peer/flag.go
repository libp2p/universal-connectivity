package main

// Things to do with flags should try to live here

import "strings"

type stringSlice []string

func (s *stringSlice) String() string {
    return strings.Join(*s, ", ")
}

func (s *stringSlice) Set(value string) error {
    *s = append(*s, value)
    return nil
}