#ifndef Py_GREENLETOBJECT_H
#define Py_GREENLETOBJECT_H


#include <Python.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GREENLET_VERSION "1.0.0"

#ifndef GREENLET_MODULE
#define implementation_ptr_t void*
#endif

typedef struct _greenlet {
    PyObject_HEAD
    PyObject* weakreflist;
    PyObject* dict;
    implementation_ptr_t pimpl;
} PyGreenlet;

#define PyGreenlet_Check(op) (op && PyObject_TypeCheck(op, &PyGreenlet_Type))

#define PyGreenlet_API_pointers 12

#define PyGreenlet_Type_NUM 0
#define PyExc_GreenletError_NUM 1
#define PyExc_GreenletExit_NUM 2

#define PyGreenlet_New_NUM 3
#define PyGreenlet_GetCurrent_NUM 4
#define PyGreenlet_Throw_NUM 5
#define PyGreenlet_Switch_NUM 6
#define PyGreenlet_SetParent_NUM 7

#define PyGreenlet_MAIN_NUM 8
#define PyGreenlet_STARTED_NUM 9
#define PyGreenlet_ACTIVE_NUM 10
#define PyGreenlet_GET_PARENT_NUM 11

#ifndef GREENLET_MODULE

static void** _PyGreenlet_API = NULL;

#    define PyGreenlet_Type \
        (*(PyTypeObject*)_PyGreenlet_API[PyGreenlet_Type_NUM])

#    define PyExc_GreenletError \
        ((PyObject*)_PyGreenlet_API[PyExc_GreenletError_NUM])

#    define PyExc_GreenletExit \
        ((PyObject*)_PyGreenlet_API[PyExc_GreenletExit_NUM])

#    define PyGreenlet_New                                        \
        (*(PyGreenlet * (*)(PyObject * run, PyGreenlet * parent)) \
             _PyGreenlet_API[PyGreenlet_New_NUM])

#    define PyGreenlet_GetCurrent \
        (*(PyGreenlet * (*)(void)) _PyGreenlet_API[PyGreenlet_GetCurrent_NUM])

#    define PyGreenlet_Throw                 \
        (*(PyObject * (*)(PyGreenlet * self, \
                          PyObject * typ,    \
                          PyObject * val,    \
                          PyObject * tb))    \
             _PyGreenlet_API[PyGreenlet_Throw_NUM])

#    define PyGreenlet_Switch                                              \
        (*(PyObject *                                                      \
           (*)(PyGreenlet * greenlet, PyObject * args, PyObject * kwargs)) \
             _PyGreenlet_API[PyGreenlet_Switch_NUM])

#    define PyGreenlet_SetParent                                 \
        (*(int (*)(PyGreenlet * greenlet, PyGreenlet * nparent)) \
             _PyGreenlet_API[PyGreenlet_SetParent_NUM])

#     define PyGreenlet_GetParent                                    \
    (*(PyGreenlet* (*)(PyGreenlet*))                                 \
     _PyGreenlet_API[PyGreenlet_GET_PARENT_NUM])

#     define PyGreenlet_GET_PARENT PyGreenlet_GetParent

#     define PyGreenlet_MAIN                                         \
    (*(int (*)(PyGreenlet*))                                         \
     _PyGreenlet_API[PyGreenlet_MAIN_NUM])

#     define PyGreenlet_STARTED                                      \
    (*(int (*)(PyGreenlet*))                                         \
     _PyGreenlet_API[PyGreenlet_STARTED_NUM])

#     define PyGreenlet_ACTIVE                                       \
    (*(int (*)(PyGreenlet*))                                         \
     _PyGreenlet_API[PyGreenlet_ACTIVE_NUM])


#    define PyGreenlet_Import()                                               \
        {                                                                     \
            _PyGreenlet_API = (void**)PyCapsule_Import("greenlet._C_API", 0); \
        }

#endif 

#ifdef __cplusplus
}
#endif
#endif
