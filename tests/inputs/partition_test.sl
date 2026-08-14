% Test file for partition constraint
% Example: Partition people into students, faculty, and staff

ExtDOM Person : Symbol.
ExtPred person : (Symbol).

[
    % Each person is in exactly one category
    student(X)? :- person(X).
    faculty(X)? :- person(X).
    staff(X)? :- person(X).
    
    % Partition constraint: Set_person = Set_student ∪ Set_faculty ∪ Set_staff (disjoint)
    (\partition Set_person {{Set_student Set_faculty Set_staff}}).
]
